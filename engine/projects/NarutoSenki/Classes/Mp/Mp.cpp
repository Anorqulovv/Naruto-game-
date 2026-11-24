// Rise of the Ninja 2.2 - local Wi-Fi multiplayer (lockstep). See Mp.h.
#include "Mp/Mp.h"
#include "GameLayer.h"
#include "HudLayer.h"
#include "HPBar.h"
#include "ActionButton.h"
#include "CharacterBase.h"
#include "StartMenu.h"
#include "Data/UnitDefines.h"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>

#include <atomic>
#include <cstdarg>
#include <chrono>
#include <condition_variable>
#include <map>
#include <mutex>
#include <random>
#include <thread>

#if (CC_TARGET_PLATFORM == CC_PLATFORM_ANDROID)
#include <jni.h>
#include <android/log.h>
#include "platform/android/jni/JniHelper.h"
#define MPLOG(...) __android_log_print(ANDROID_LOG_INFO, "ROTN-MP", __VA_ARGS__)
#else
#define MPLOG(...) CCLOG(__VA_ARGS__)
#endif

namespace mp
{
	static const int kPort = 7777;
	static const int kInputDelay = 6;	   // frames between a touch and its effect (~100 ms)
	static const int kMaxPlayers = 6;
	static const int kTimeoutMs = 3000;	   // a silent player is replaced by a bot after this
	static const uint32_t kVersion = 220;

	enum Role { Off = 0, Host = 1, Client = 2 };

	struct Command { uint8_t type; int16_t a, b; };
	using Commands = std::vector<Command>;

	struct Bundle
	{
		std::vector<std::pair<int, Commands>> cmds; // player id -> commands
		std::vector<int> gone;						// players replaced by bots at this frame
	};

	struct Conn // host side, one per client
	{
		int sock = -1;
		int id = 0;
		int team = 0; // 0 with the host, 1 against
		bool picked = false;
		std::string pick;
		bool gone = false;
		bool goneSent = false;
		std::map<int64_t, Commands> inputs; // frame -> commands
		int64_t lastSeenMs = 0;
	};

	static std::recursive_mutex mu;
	static std::atomic<int> s_role{Off};
	static std::atomic<int> s_session{0};
	static std::string s_status = "off";
	static std::string s_hostIp;

	// host
	static std::vector<Conn *> s_conns;
	static int s_listen = -1;
	static bool s_hostPicked = false;
	static std::string s_hostPick;
	static int s_hostMode = 1;
	// client
	static int s_sock = -1;
	static int s_myId = 0;
	static int s_myTeam = 0;
	static bool s_hostGone = false;
	static std::map<int64_t, Bundle> s_bundles;
	static std::map<int64_t, uint32_t> s_hostSums; // host: own checksums by frame

	// line-up
	static bool s_waitingLineup = false;
	static bool s_haveLineup = false;
	static std::vector<LineupEntry> s_lineup;
	static uint32_t s_seed = 1;
	static int s_mode = 1;
	static uint8_t s_hostGroup = 0;

	// battle
	static bool s_battle = false;
	static bool s_solo = false; // the host left: continue alone without lockstep
	static int64_t s_frame = 0;
	static Commands s_pending;			   // captured locally since the last frame
	static std::map<int64_t, Commands> s_own; // host: own scheduled commands
	static std::map<int, CharacterBase *> s_heroOf;
	static std::map<CharacterBase *, bool> s_released;
	static int64_t s_stallSince = 0;
	static bool s_desyncReported = false;
	static float s_lastWalkX = 99, s_lastWalkY = 99;
	static std::atomic<bool> s_paused{false};
	static bool s_gated = false; // this scheduler tick was a lockstep frame
	static int64_t s_sentFor = -1;
	static int64_t s_hostSeenMs = 0; // client: last message from the host

	// deterministic random numbers (drand48 style LCG)
	static bool s_det = false;
	static uint64_t s_rng = 0x1234ABCD330EULL;

	static int64_t nowMs()
	{
		return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
	}

	static void setStatus(const std::string &s)
	{
		std::lock_guard<std::recursive_mutex> lk(mu);
		if (s_status != s)
			MPLOG("status: %s", s.c_str());
		s_status = s;
	}

	// ------------------------------------------------------------------ random numbers
	static uint32_t rngNext()
	{
		s_rng = (s_rng * 0x5DEECE66DULL + 0xB) & ((1ULL << 48) - 1);
		return (uint32_t)(s_rng >> 17);
	}
	static void reseed(uint32_t seed) { s_rng = ((uint64_t)seed << 16) | 0x330E; }

	int rngRandom(int x)
	{
		if (x <= 0)
			return 0;
		if (s_det)
			return (int)(rngNext() % (uint32_t)x);
		return (::rand)() % x;
	}
	void rngSetRand()
	{
		if (!s_det)
			srand((uint32_t)time(0));
	}
	int logicRand()
	{
		if (!s_det)
			return (::rand)();
		return (int)(rngNext() & 0x7fffffff);
	}

	bool active() { return s_role != Off; }
	bool inBattle() { return s_battle; }
	bool isHost() { return s_role == Host; }
	bool isClient() { return s_role == Client; }
	int myId() { return s_myId; }

	// ------------------------------------------------------------------ wire helpers
	static bool sendAll(int s, const void *p, size_t n)
	{
		const char *c = (const char *)p;
		while (n)
		{
			ssize_t r = ::send(s, c, n, MSG_NOSIGNAL);
			if (r <= 0)
				return false;
			c += r, n -= r;
		}
		return true;
	}
	static bool recvAll(int s, void *p, size_t n)
	{
		char *c = (char *)p;
		while (n)
		{
			ssize_t r = ::recv(s, c, n, 0);
			if (r <= 0)
				return false;
			c += r, n -= r;
		}
		return true;
	}

	struct Writer
	{
		std::vector<uint8_t> b;
		Writer(char type) { b.resize(4); b.push_back((uint8_t)type); }
		void u8(uint8_t v) { b.push_back(v); }
		void i16(int16_t v) { b.push_back(v & 0xff); b.push_back((v >> 8) & 0xff); }
		void u32(uint32_t v) { for (int i = 0; i < 4; i++) b.push_back((v >> (8 * i)) & 0xff); }
		void i64(int64_t v) { for (int i = 0; i < 8; i++) b.push_back(((uint64_t)v >> (8 * i)) & 0xff); }
		void str(const std::string &s) { u8((uint8_t)s.size()); b.insert(b.end(), s.begin(), s.end()); }
		void cmds(const Commands &c)
		{
			u8((uint8_t)c.size());
			for (auto &x : c) { u8(x.type); i16(x.a); i16(x.b); }
		}
		const std::vector<uint8_t> &done()
		{
			uint32_t n = (uint32_t)b.size() - 4;
			for (int i = 0; i < 4; i++) b[i] = (n >> (8 * i)) & 0xff;
			return b;
		}
	};
	struct Reader
	{
		std::vector<uint8_t> b;
		size_t p = 0;
		bool ok = true;
		uint8_t u8() { if (p + 1 > b.size()) { ok = false; return 0; } return b[p++]; }
		int16_t i16() { uint16_t v = u8(); v |= (uint16_t)u8() << 8; return (int16_t)v; }
		uint32_t u32() { uint32_t v = 0; for (int i = 0; i < 4; i++) v |= (uint32_t)u8() << (8 * i); return v; }
		int64_t i64() { uint64_t v = 0; for (int i = 0; i < 8; i++) v |= (uint64_t)u8() << (8 * i); return (int64_t)v; }
		std::string str() { size_t n = u8(); if (p + n > b.size()) { ok = false; return ""; } std::string s(b.begin() + p, b.begin() + p + n); p += n; return s; }
		Commands cmds()
		{
			Commands c(u8());
			for (auto &x : c) { x.type = u8(); x.a = i16(); x.b = i16(); }
			return c;
		}
	};
	static std::mutex sendMu;
	static bool sendMsg(int s, Writer &w)
	{
		std::lock_guard<std::mutex> lk(sendMu);
		auto &b = w.done();
		return s >= 0 && sendAll(s, b.data(), b.size());
	}
	static bool readMsg(int s, char &type, Reader &r)
	{
		uint8_t h[4];
		if (!recvAll(s, h, 4))
			return false;
		uint32_t n = h[0] | (h[1] << 8) | (h[2] << 16) | ((uint32_t)h[3] << 24);
		if (n == 0 || n > (1 << 20))
			return false;
		r.b.resize(n);
		if (!recvAll(s, r.b.data(), n))
			return false;
		type = (char)r.b[0];
		r.p = 1;
		return true;
	}
	static void tune(int s)
	{
		int one = 1;
		setsockopt(s, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
	}

	// ------------------------------------------------------------------ room status
	static std::string roomStatus()
	{
		int n = 0, a = 0, b = 0;
		for (auto *c : s_conns)
			if (!c->gone)
			{
				n++;
				(c->team ? b : a)++;
			}
		char buf[96];
		snprintf(buf, sizeof buf, "room open: %d players joined %d %d", n, a, b);
		return buf;
	}

	// ------------------------------------------------------------------ host networking
	static void hostReader(Conn *c, int session)
	{
		for (;;)
		{
			char type;
			Reader r;
			if (!readMsg(c->sock, type, r))
				break;
			std::lock_guard<std::recursive_mutex> lk(mu);
			if (session != s_session)
				return;
			c->lastSeenMs = nowMs();
			if (type == 'H' || type == 'T')
			{
				c->team = r.u8() ? 1 : 0;
				if (!s_battle && !s_haveLineup)
					setStatus(roomStatus());
			}
			else if (type == 'P')
			{
				c->pick = r.str();
				c->picked = true;
			}
			else if (type == 'F')
			{
				int64_t f = r.i64();
				c->inputs[f] = r.cmds();
			}
			else if (type == 'C')
			{
				int64_t f = r.i64();
				uint32_t sum = r.u32();
				auto it = s_hostSums.find(f);
				if (it != s_hostSums.end() && it->second != sum && !s_desyncReported)
				{
					s_desyncReported = true;
					MPLOG("DESYNC with player %d at frame %lld (%08x vs %08x)", c->id, (long long)f, it->second, sum);
					setStatus("warning: desync");
				}
			}
			else if (type == 'X')
				break;
			// 'K' (keep-alive) only refreshes lastSeenMs
		}
		std::lock_guard<std::recursive_mutex> lk(mu);
		if (session != s_session)
			return;
		c->gone = true;
		::close(c->sock);
		c->sock = -1;
		MPLOG("player %d left", c->id);
		if (!s_battle && !s_haveLineup)
			setStatus(roomStatus());
	}

	static void hostListener(int session, int ls)
	{
		for (;;)
		{
			sockaddr_in a{};
			socklen_t al = sizeof a;
			int s = ::accept(ls, (sockaddr *)&a, &al);
			if (s < 0)
				return;
			tune(s);
			std::lock_guard<std::recursive_mutex> lk(mu);
			if (session != s_session)
			{
				::close(s);
				return;
			}
			int alive = 0;
			for (auto *c : s_conns)
				if (!c->gone)
					alive++;
			if (s_haveLineup || s_battle || alive >= kMaxPlayers - 1)
			{
				Writer w('X');
				sendMsg(s, w);
				::close(s);
				continue;
			}
			auto *c = new Conn();
			c->sock = s;
			c->id = 1;
			for (bool used = true; used;)
			{
				used = false;
				for (auto *o : s_conns)
					if (o->id == c->id && !o->gone)
						used = true, c->id++;
			}
			c->lastSeenMs = nowMs();
			s_conns.push_back(c);
			Writer w('W');
			w.u8((uint8_t)c->id);
			w.u32(kVersion);
			sendMsg(s, w);
			std::thread(hostReader, c, session).detach();
			setStatus(roomStatus());
		}
	}

	// ------------------------------------------------------------------ client networking
	static void clientThread(int session, std::string ip, int team)
	{
		setStatus("connecting");
		int s = ::socket(AF_INET, SOCK_STREAM, 0);
		sockaddr_in a{};
		a.sin_family = AF_INET;
		a.sin_port = htons(kPort);
		inet_pton(AF_INET, ip.c_str(), &a.sin_addr);
		// connect with a timeout
		fcntl(s, F_SETFL, fcntl(s, F_GETFL) | O_NONBLOCK);
		int r = ::connect(s, (sockaddr *)&a, sizeof a);
		if (r < 0 && errno == EINPROGRESS)
		{
			pollfd p{s, POLLOUT, 0};
			if (::poll(&p, 1, 4000) == 1)
			{
				int err = 0;
				socklen_t el = sizeof err;
				getsockopt(s, SOL_SOCKET, SO_ERROR, &err, &el);
				r = err ? -1 : 0;
			}
			else
				r = -1;
		}
		fcntl(s, F_SETFL, fcntl(s, F_GETFL) & ~O_NONBLOCK);
		if (r < 0)
		{
			::close(s);
			if (session == s_session)
				setStatus("could not reach the room");
			return;
		}
		tune(s);
		{
			std::lock_guard<std::recursive_mutex> lk(mu);
			if (session != s_session)
			{
				::close(s);
				return;
			}
			s_sock = s;
		}
		{
			Writer w('H');
			w.u8((uint8_t)team);
			sendMsg(s, w);
		}
		for (;;)
		{
			char type;
			Reader rd;
			if (!readMsg(s, type, rd))
				break;
			std::lock_guard<std::recursive_mutex> lk(mu);
			if (session != s_session)
				return;
			s_hostSeenMs = nowMs();
			if (type == 'W')
			{
				s_myId = rd.u8();
				setStatus("connected");
			}
			else if (type == 'L')
			{
				s_seed = rd.u32();
				s_mode = rd.u8();
				s_hostGroup = rd.u8();
				int n = rd.u8();
				s_lineup.clear();
				for (int i = 0; i < n; i++)
				{
					LineupEntry e;
					e.name = rd.str();
					e.group = rd.u8();
					e.owner = (int8_t)rd.u8();
					s_lineup.push_back(e);
				}
				s_haveLineup = true;
				MPLOG("line-up received: %d heroes, mode %d, seed %u", n, s_mode, s_seed);
			}
			else if (type == 'B')
			{
				int64_t f = rd.i64();
				Bundle b;
				int n = rd.u8();
				for (int i = 0; i < n; i++)
				{
					int id = rd.u8();
					b.cmds.push_back({id, rd.cmds()});
				}
				int g = rd.u8();
				for (int i = 0; i < g; i++)
					b.gone.push_back(rd.u8());
				s_bundles[f] = std::move(b);
			}
			else if (type == 'X')
			{
				if (!s_haveLineup && !s_battle)
				{
					setStatus("the room is full");
					::close(s);
					s_sock = -1;
					return;
				}
				break;
			}
		}
		std::lock_guard<std::recursive_mutex> lk(mu);
		if (session != s_session)
			return;
		::close(s);
		s_sock = -1;
		s_hostGone = true;
		setStatus(s_battle ? "the host left" : "the host left the room");
	}

	// ------------------------------------------------------------------ configuration (Java lobby)
	static void resetLocked()
	{
		s_session++;
		if (s_listen >= 0)
		{
			::shutdown(s_listen, SHUT_RDWR);
			::close(s_listen);
			s_listen = -1;
		}
		for (auto *c : s_conns)
			if (c->sock >= 0)
			{
				Writer w('X');
				sendMsg(c->sock, w);
				::shutdown(c->sock, SHUT_RDWR);
			}
		s_conns.clear(); // readers exit on the session check (small leak by design)
		if (s_sock >= 0)
		{
			Writer w('X');
			sendMsg(s_sock, w);
			::shutdown(s_sock, SHUT_RDWR);
			s_sock = -1;
		}
		s_role = Off;
		s_myId = 0;
		s_hostGone = false;
		s_hostPicked = false;
		s_waitingLineup = false;
		s_haveLineup = false;
		s_lineup.clear();
		s_bundles.clear();
		s_hostSums.clear();
		s_battle = false;
		s_solo = false;
		s_det = false;
		s_own.clear();
		s_pending.clear();
		s_heroOf.clear();
		s_released.clear();
		s_desyncReported = false;
	}

	// keep-alive: a player that stops answering (app in the background) is replaced by a bot
	static void heartbeat(int session)
	{
		while (session == s_session)
		{
			std::this_thread::sleep_for(std::chrono::milliseconds(500));
			if (s_paused)
				continue;
			std::lock_guard<std::recursive_mutex> lk(mu);
			if (session != s_session)
				return;
			Writer w('K');
			if (s_role == Host)
			{
				for (auto *c : s_conns)
					if (!c->gone)
						sendMsg(c->sock, w);
			}
			else if (s_sock >= 0)
				sendMsg(s_sock, w);
		}
	}

	void appPaused(bool p) { s_paused = p; }


	void configure(int role, const char *ip)
	{
		std::lock_guard<std::recursive_mutex> lk(mu);
		resetLocked();
		if (role == 0)
		{
			setStatus("off");
			return;
		}
		int session = s_session;
		if (role == 1)
		{
			int ls = ::socket(AF_INET, SOCK_STREAM, 0);
			int one = 1;
			setsockopt(ls, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
			sockaddr_in a{};
			a.sin_family = AF_INET;
			a.sin_port = htons(kPort);
			a.sin_addr.s_addr = INADDR_ANY;
			if (::bind(ls, (sockaddr *)&a, sizeof a) < 0 || ::listen(ls, 8) < 0)
			{
				::close(ls);
				setStatus("cannot open a room");
				return;
			}
			s_listen = ls;
			s_role = Host;
			s_myId = 0;
			setStatus(roomStatus());
			std::thread(hostListener, session, ls).detach();
			std::thread(heartbeat, session).detach();
		}
		else
		{
			s_role = Client;
			s_myTeam = role == 4 ? 1 : 0;
			s_hostIp = ip ? ip : "";
			std::thread(clientThread, session, s_hostIp, s_myTeam).detach();
			std::thread(heartbeat, session).detach();
		}
	}

	void setTeam(int t)
	{
		std::lock_guard<std::recursive_mutex> lk(mu);
		s_myTeam = t ? 1 : 0;
		if (s_role == Client && s_sock >= 0 && !s_haveLineup)
		{
			Writer w('T');
			w.u8((uint8_t)s_myTeam);
			sendMsg(s_sock, w);
		}
	}
	int team() { return s_myTeam; }

	std::string status()
	{
		std::lock_guard<std::recursive_mutex> lk(mu);
		return s_status;
	}

	std::string busy()
	{
		std::lock_guard<std::recursive_mutex> lk(mu);
		if (s_waitingLineup && !s_haveLineup)
			return s_role == Host ? "wait:players" : "wait:host";
		if (s_battle && !s_solo && s_stallSince && nowMs() - s_stallSince > 300)
			return "wait:net";
		return "";
	}

	// ------------------------------------------------------------------ line-up
	static int teamSize(int mode)
	{
		if (mode == GameMode::OneVsOne)
			return 1;
		if (mode == GameMode::FourVsFour) // the 2 VS 2 slot
			return 2;
		return 3;
	}

	static bool tryBuildLineupLocked()
	{
		// host: everybody connected has picked a hero
		for (auto *c : s_conns)
			if (!c->gone && !c->picked)
				return false;
		std::mt19937 g((uint32_t)nowMs());
		int n = teamSize(s_hostMode);
		uint8_t hostGroup = (uint8_t)(g() % 2);
		std::vector<std::string> used;
		auto valid = [&](const std::string &h) {
			if (h.empty() || h == "None" || h == "None2")
				return false;
			bool known = false;
			for (auto *k : kHeroList)
				if (h == k)
					known = true;
			if (!known)
				return false;
			for (auto &u : used)
				if (heroFamily(u) == heroFamily(h))
					return false;
			return true;
		};
		auto randomHero = [&]() {
			std::vector<std::string> free;
			for (auto *k : kHeroList)
				if (valid(k))
					free.push_back(k);
			return free[g() % free.size()];
		};
		std::vector<LineupEntry> ally, rival;
		auto place = [&](int id, std::string pick, int team) {
			if (!valid(pick))
				pick = randomHero();
			auto &want = team ? rival : ally;
			auto &other = team ? ally : rival;
			auto *side = (int)want.size() < n ? &want : ((int)other.size() < n ? &other : nullptr);
			if (!side)
				return; // no room left: this player watches
			used.push_back(pick);
			uint8_t grp = side == &ally ? hostGroup : (uint8_t)(1 - hostGroup);
			side->push_back({pick, grp, (int8_t)id});
		};
		place(0, s_hostPick, 0);
		for (auto *c : s_conns)
			if (!c->gone)
				place(c->id, c->pick, c->team);
		while ((int)ally.size() < n)
		{
			auto h = randomHero();
			used.push_back(h);
			ally.push_back({h, hostGroup, -1});
		}
		while ((int)rival.size() < n)
		{
			auto h = randomHero();
			used.push_back(h);
			rival.push_back({h, (uint8_t)(1 - hostGroup), -1});
		}
		s_lineup = ally; // the host is first: it becomes the game's player
		s_lineup.insert(s_lineup.end(), rival.begin(), rival.end());
		s_seed = g();
		s_mode = s_hostMode;
		s_hostGroup = hostGroup;
		Writer w('L');
		w.u32(s_seed);
		w.u8((uint8_t)s_mode);
		w.u8(s_hostGroup);
		w.u8((uint8_t)s_lineup.size());
		for (auto &e : s_lineup)
		{
			w.str(e.name);
			w.u8(e.group);
			w.u8((uint8_t)e.owner);
		}
		for (auto *c : s_conns)
			if (!c->gone)
				sendMsg(c->sock, w);
		s_haveLineup = true;
		MPLOG("line-up sent: %d heroes, mode %d", (int)s_lineup.size(), s_mode);
		return true;
	}

	bool requestStart(const char *hero)
	{
		std::lock_guard<std::recursive_mutex> lk(mu);
		if (s_role == Off)
			return false;
		if (s_role == Client && (s_sock < 0 || s_hostGone))
			return false; // not connected: play offline
		s_waitingLineup = true;
		std::string pick = hero ? hero : "";
		if (s_role == Host)
		{
			s_hostPick = pick;
			s_hostPicked = true;
			s_hostMode = s_GameMode;
			setStatus("waiting for the players");
		}
		else
		{
			Writer w('P');
			w.str(pick);
			sendMsg(s_sock, w);
			setStatus("waiting for the host");
		}
		return true;
	}

	bool lineupReady()
	{
		std::lock_guard<std::recursive_mutex> lk(mu);
		if (s_role == Host && !s_haveLineup && s_hostPicked)
			tryBuildLineupLocked();
		if (s_role == Client && s_hostGone)
			return true; // fall back to an offline game
		return s_haveLineup;
	}

	bool hasLineup() { return s_haveLineup && s_waitingLineup; }
	const std::vector<LineupEntry> &lineup() { return s_lineup; }
	uint8_t hostGroup() { return s_hostGroup; }

	void applyLineupToMode()
	{
		if (!hasLineup())
			return;
		s_GameMode = (GameMode)s_mode;
		auto *h = getGameModeHandler();
		h->init();
	}

	// ------------------------------------------------------------------ battle
	void battlePrepare()
	{
		std::lock_guard<std::recursive_mutex> lk(mu);
		if (!hasLineup())
			return;
		s_battle = true;
		s_solo = false;
		s_det = true;
		reseed(s_seed);
		s_frame = 0;
		s_pending.clear();
		s_own.clear();
		s_bundles.erase(s_bundles.begin(), s_bundles.lower_bound(0));
		s_heroOf.clear();
		s_released.clear();
		s_stallSince = 0;
		s_sentFor = -1;
		s_hostSeenMs = nowMs();
		s_lastWalkX = s_lastWalkY = 99;
		s_waitingLineup = false; // the line-up is consumed by this battle
		int humans = 0;
		bool rival = false, watching = true;
		for (auto &e : s_lineup)
			if (e.owner >= 0)
			{
				humans++;
				if (e.owner == s_myId)
					watching = false, rival = e.group != s_hostGroup;
			}
		char buf[96];
		snprintf(buf, sizeof buf, "battle: %d players%s", humans,
				 s_role == Host ? ", you are the host" : watching ? ", watching" : rival ? " (rival)" : " (team)");
		setStatus(buf);
		s_haveLineup = true;
	}

	void battleHeroesCreated(GameLayer *gl)
	{
		std::lock_guard<std::recursive_mutex> lk(mu);
		if (!s_battle)
			return;
		for (auto &e : s_lineup)
		{
			if (e.owner < 0)
				continue;
			for (auto *c : gl->_CharacterArray)
				if (c->getName() == e.name)
					s_heroOf[e.owner] = c;
		}
		auto it = s_heroOf.find(s_myId);
		gl->viewPlayer = (s_role == Client && it != s_heroOf.end()) ? it->second : nullptr;
		if (!gl->viewPlayer)
			return;
		// HP bar colours as seen by this phone's hero
		auto *v = gl->viewPlayer;
		for (auto *c : gl->_CharacterArray)
			if (c->_hpBar)
				c->_hpBar->changeBar(c->getGroup() != v->getGroup() ? "hp_bar_r.png" : c == v ? "hp_bar.png" : "hp_bar_b.png");
		for (auto *t : gl->_TowerArray)
			if (t && t->_hpBar)
				t->_hpBar->changeBar(t->getGroup() != v->getGroup() ? "hp_bar_r.png" : "hp_bar.png");
	}

	bool isRemoteHuman(CharacterBase *c)
	{
		if (!s_battle || s_solo && c != myHero())
			return false;
		for (auto &kv : s_heroOf)
			if (kv.second == c)
				return !c->isPlayer();
		return false;
	}

	CharacterBase *myHero()
	{
		auto it = s_heroOf.find(s_myId);
		return it == s_heroOf.end() ? nullptr : it->second;
	}

	bool attackReleased(CharacterBase *c)
	{
		if (c->isPlayer())
			return getGameLayer()->_isAttackButtonRelease;
		auto it = s_released.find(c);
		return it == s_released.end() ? true : it->second;
	}

	void battleOver()
	{
		std::lock_guard<std::recursive_mutex> lk(mu);
		if (!s_battle)
			return;
		MPLOG("battle over at frame %lld", (long long)s_frame);
		// the room stays open for another game; the next line-up starts from scratch
		s_battle = false;
		s_det = false;
		s_haveLineup = false;
		s_waitingLineup = false;
		s_heroOf.clear();
		s_released.clear();
		s_bundles.clear();
		s_hostSums.clear();
		s_own.clear();
		s_hostPicked = false;
		for (auto *c : s_conns)
		{
			c->picked = false;
			c->inputs.clear();
			c->goneSent = c->gone;
		}
		if (s_role == Host)
			setStatus(roomStatus());
		else if (!s_hostGone)
			setStatus("connected");
		else
			s_role = Off, setStatus("off");
	}

	// ------------------------------------------------------------------ commands
	static void applyOne(CharacterBase *h, const Command &c)
	{
		auto *gl = getGameLayer();
		if (!h || !gl)
			return;
		switch (c.type)
		{
		case CmdWalk:
			if (h->isPlayer() && gl->ougisChar)
				return;
			h->walk(Vec2(c.a / 10000.0f, c.b / 10000.0f));
			break;
		case CmdIdle:
			if (h->getState() == State::WALK)
				h->idle();
			break;
		case CmdRelease:
			if (h->isPlayer())
				gl->_isAttackButtonRelease = true;
			else
				s_released[h] = true;
			break;
		case CmdAttack:
		{
			auto type = (ABType)c.a;
			if (type == NAttack)
			{
				if (h->isPlayer())
					gl->_isAttackButtonRelease = false;
				else
					s_released[h] = false;
				h->attack(type);
			}
			else if (type == Item1)
			{
				if (h->getCoin() < 50 || h->getState() == State::DEAD)
					return;
				if (h->isPlayer())
					h->minusCoin(50); // what the HUD does for the local player
				h->setItem(type);
			}
			else if (type == OUGIS1 || type == OUGIS2)
			{
				uint32_t cost = type == OUGIS1 ? 15000 : 25000;
				uint32_t have = type == OUGIS1 ? h->getCKR() : h->getCKR2();
				if (have < cost)
					return;
				if (h->isPlayer())
				{
					if (type == OUGIS1)
						h->setCKR(have - cost);
					else
						h->setCKR2(have - cost);
				}
				h->attack(type);
				if (h == gl->view())
					gl->setCKRLose(type == OUGIS2);
			}
			else
				h->attack(type);
			break;
		}
		case CmdUseGear:
			h->useGear((GearType)c.a);
			break;
		case CmdBuyGear:
			h->setGear((GearType)c.a);
			break;
		}
	}

	static void applyBundle(const Bundle &b)
	{
		for (auto &pc : b.cmds)
		{
			auto it = s_heroOf.find(pc.first);
			if (it == s_heroOf.end())
				continue;
			for (auto &c : pc.second)
				applyOne(it->second, c);
		}
		for (int id : b.gone)
		{
			auto it = s_heroOf.find(id);
			if (it == s_heroOf.end())
				continue;
			auto *h = it->second;
			s_heroOf.erase(it);
			MPLOG("player %d is replaced by a bot at frame %lld", id, (long long)s_frame);
			if (!h->isPlayer())
				h->doAI();
		}
	}

	void localWalk(float x, float y)
	{
		int16_t a = (int16_t)(x * 10000), b = (int16_t)(y * 10000);
		if (std::abs(a - s_lastWalkX * 10000) < 400 && std::abs(b - s_lastWalkY * 10000) < 400)
			return; // small changes are not worth a command
		s_lastWalkX = x, s_lastWalkY = y;
		std::lock_guard<std::recursive_mutex> lk(mu);
		s_pending.push_back({CmdWalk, a, b});
	}

	void localCmd(Cmd c, int a)
	{
		if (c == CmdIdle)
			s_lastWalkX = s_lastWalkY = 99;
		std::lock_guard<std::recursive_mutex> lk(mu);
		if (s_solo)
		{
			// the host left: my hero is driven directly
			if (auto *h = myHero())
				applyOne(h, {(uint8_t)c, (int16_t)a, 0});
			return;
		}
		s_pending.push_back({(uint8_t)c, (int16_t)a, 0});
	}

	// ------------------------------------------------------------------ frame loop
	static uint32_t checksum()
	{
		uint32_t h = 2166136261u;
		auto mix = [&](uint32_t v) { h = (h ^ v) * 16777619u; };
		auto *gl = getGameLayer();
		if (gl)
			for (auto *c : gl->_CharacterArray)
			{
				for (char ch : c->getName())
					mix((uint8_t)ch);
				mix((uint32_t)(int)(c->getPositionX() * 8));
				mix((uint32_t)(int)(c->getPositionY() * 8));
				mix(c->getHP());
				mix(c->getCKR());
				mix(c->getCKR2());
				mix((uint32_t)c->getState());
			}
		mix((uint32_t)s_rng);
		mix((uint32_t)(s_rng >> 32));
		return h;
	}

	static void goSolo()
	{
		// the host vanished: everybody else becomes a bot, I keep playing my hero
		s_solo = true;
		std::vector<CharacterBase *> others;
		for (auto &kv : s_heroOf)
			if (kv.first != s_myId)
				others.push_back(kv.second);
		for (auto *h : others)
			h->doAI();
		auto *me = myHero();
		s_heroOf.clear();
		if (me)
			s_heroOf[s_myId] = me;
		MPLOG("continuing alone");
	}

	static bool stepGateInner();
	// Called once per rendered frame before the scheduler update: may we simulate the next frame?
	bool stepGate()
	{
		s_gated = false;
		if (!s_battle || s_solo)
			return true;
		if (stepGateInner())
			return s_gated = true;
		return false;
	}

	static bool stepGateInner()
	{
		std::lock_guard<std::recursive_mutex> lk(mu);
		int64_t f = s_frame;
		if (s_role == Host)
		{
			// my own commands go to frame f + delay
			if (!s_own.count(f + kInputDelay))
				s_own[f + kInputDelay] = std::move(s_pending), s_pending.clear();
			Bundle b;
			auto mine = s_own.find(f);
			b.cmds.push_back({0, mine == s_own.end() ? Commands() : mine->second});
			int64_t now = nowMs();
			bool missing = false;
			for (auto *c : s_conns)
			{
				if (c->goneSent)
					continue;
				if (c->gone)
				{
					b.gone.push_back(c->id);
					continue;
				}
				auto it = c->inputs.find(f);
				if (it != c->inputs.end())
					b.cmds.push_back({c->id, it->second}), c->inputs.erase(it);
				else if (f < kInputDelay)
					; // nobody can have sent input for the first frames
				else if (now - c->lastSeenMs > kTimeoutMs)
				{
					MPLOG("player %d is silent: a bot takes over", c->id);
					c->gone = true;
					b.gone.push_back(c->id);
				}
				else
					missing = true;
			}
			if (missing)
			{
				if (!s_stallSince)
					s_stallSince = now;
				return false;
			}
			for (auto *c : s_conns)
				if (c->gone && !c->goneSent && std::find(b.gone.begin(), b.gone.end(), c->id) != b.gone.end())
					c->goneSent = true;
			s_stallSince = 0;
			Writer w('B');
			w.i64(f);
			w.u8((uint8_t)b.cmds.size());
			for (auto &pc : b.cmds)
			{
				w.u8((uint8_t)pc.first);
				w.cmds(pc.second);
			}
			w.u8((uint8_t)b.gone.size());
			for (int id : b.gone)
				w.u8((uint8_t)id);
			for (auto *c : s_conns)
				if (!c->gone)
					if (!sendMsg(c->sock, w))
						c->gone = true;
			s_own.erase(f);
			applyBundle(b);
			return true;
		}
		// client
		if (s_hostGone)
		{
			goSolo();
			return true;
		}
		// send my commands for frame f + delay once
		if (s_sentFor != f + kInputDelay)
		{
			Writer w('F');
			w.i64(f + kInputDelay);
			w.cmds(s_pending);
			sendMsg(s_sock, w);
			s_pending.clear();
			s_sentFor = f + kInputDelay;
		}
		auto it = s_bundles.find(f);
		if (it == s_bundles.end())
		{
			int64_t now = nowMs();
			if (!s_stallSince)
				s_stallSince = now;
			if (now - s_hostSeenMs > 10000 && now - s_stallSince > 10000)
			{
				MPLOG("the host is silent: continuing alone");
				s_hostGone = true;
				setStatus("the host left");
				goSolo();
				return true;
			}
			return false;
		}
		s_stallSince = 0;
		Bundle b = std::move(it->second);
		s_bundles.erase(it);
		applyBundle(b);
		return true;
	}

	void afterStep()
	{
		if (!s_battle || (!s_gated && !s_solo))
			return; // e.g. the loading tick that started the battle is not a lockstep frame
		s_gated = false;
		std::lock_guard<std::recursive_mutex> lk(mu);
		if (!s_solo && s_frame % 60 == 0)
		{
			uint32_t sum = checksum();
			if (s_frame % 600 == 0)
				MPLOG("frame %lld sum %08x", (long long)s_frame, sum);

			if (s_role == Host)
			{
				s_hostSums[s_frame] = sum;
				while (s_hostSums.size() > 200)
					s_hostSums.erase(s_hostSums.begin());
			}
			else if (s_sock >= 0)
			{
				Writer w('C');
				w.i64(s_frame);
				w.u32(sum);
				sendMsg(s_sock, w);
			}
		}
		s_frame++;
		// the client's HUD shows its own hero
		auto *gl = getGameLayer();
		if (gl && gl->viewPlayer && s_frame % 6 == 0)
		{
			auto *v = gl->viewPlayer;
			auto *hud = gl->getHudLayer();
			if (hud && hud->hpLabel)
			{
				hud->setHPLose(v->getHpPercent());
				hud->coinLabel->setString(to_cstr(v->getCoin()));
				hud->setEXPLose();
				if (hud->skill4Button && !hud->skill4Button->lockLabel1)
					hud->setCKRLose(false);
				if (hud->skill5Button && !hud->skill5Button->lockLabel1)
					hud->setCKRLose(true);
			}
		}
	}

	bool virtualTime(cocos2d::cc_timeval *tv)
	{
		if (!s_battle || s_solo)
			return false;
		int64_t us = 1600000000LL * 1000000LL + s_frame * 16667LL;
		tv->tv_sec = (long)(us / 1000000);
		tv->tv_usec = (long)(us % 1000000);
		return true;
	}

	// ------------------------------------------------------------------ Java lobby
	void openLobby()
	{
#if (CC_TARGET_PLATFORM == CC_PLATFORM_ANDROID)
		JniMethodInfo mi;
		if (JniHelper::getStaticMethodInfo(mi, "re/naruto/game/MultiplayerUi", "openLobby", "()V"))
		{
			mi.env->CallStaticVoidMethod(mi.classID, mi.methodID);
			mi.env->DeleteLocalRef(mi.classID);
		}
#endif
	}
} // namespace mp

// Engine hooks (declared extern in CCDirector.cpp / CCTime.cpp)
bool ns_mp_step_gate() { return mp::stepGate(); }
void ns_mp_after_step() { mp::afterStep(); }
bool ns_mp_virtual_time(cocos2d::cc_timeval *tv) { return mp::virtualTime(tv); }
bool ns_mp_fixed_dt() { return mp::inBattle(); }
int ns_random(int x) { return mp::rngRandom(x); }
void ns_setRand() { mp::rngSetRand(); }
int ns_rand() { return mp::logicRand(); }

#if (CC_TARGET_PLATFORM == CC_PLATFORM_ANDROID)
extern "C"
{
	JNIEXPORT jstring JNICALL Java_re_naruto_game_MultiplayerUi_nativeMpStatus(JNIEnv *env, jclass)
	{
		return env->NewStringUTF(mp::status().c_str());
	}
	JNIEXPORT jstring JNICALL Java_re_naruto_game_MultiplayerUi_nativeBusy(JNIEnv *env, jclass)
	{
		return env->NewStringUTF(mp::busy().c_str());
	}
	JNIEXPORT void JNICALL Java_re_naruto_game_MultiplayerUi_nativeMpConfigure(JNIEnv *env, jclass, jint role, jstring ip)
	{
		const char *s = ip ? env->GetStringUTFChars(ip, nullptr) : nullptr;
		mp::configure(role, s);
		if (s)
			env->ReleaseStringUTFChars(ip, s);
	}
	JNIEXPORT void JNICALL Java_re_naruto_game_MultiplayerUi_nativeMpSetTeam(JNIEnv *, jclass, jint t) { mp::setTeam(t); }
	JNIEXPORT jint JNICALL Java_re_naruto_game_MultiplayerUi_nativeMpTeam(JNIEnv *, jclass) { return mp::team(); }
	JNIEXPORT void JNICALL Java_re_naruto_game_MultiplayerUi_nativeAppPaused(JNIEnv *, jclass, jboolean p) { mp::appPaused(p); }
}
#endif

// RotN 2.2 Wi-Fi battle: every object starts from zeroed memory, so a member the original code forgot
// to initialise has the same value on every phone (otherwise phones drift apart).
#include <new>
#include <cstdlib>
void *operator new(std::size_t n)
{
	void *p = std::calloc(1, n ? n : 1);
	if (!p)
		throw std::bad_alloc();
	return p;
}
void *operator new[](std::size_t n) { return operator new(n); }
void *operator new(std::size_t n, const std::nothrow_t &) noexcept { return std::calloc(1, n ? n : 1); }
void *operator new[](std::size_t n, const std::nothrow_t &) noexcept { return std::calloc(1, n ? n : 1); }
void operator delete(void *p) noexcept { std::free(p); }
void operator delete[](void *p) noexcept { std::free(p); }
void operator delete(void *p, std::size_t) noexcept { std::free(p); }
void operator delete[](void *p, std::size_t) noexcept { std::free(p); }
void operator delete(void *p, const std::nothrow_t &) noexcept { std::free(p); }
void operator delete[](void *p, const std::nothrow_t &) noexcept { std::free(p); }
