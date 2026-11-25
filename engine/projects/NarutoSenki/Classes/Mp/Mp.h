#pragma once
// Rise of the Ninja 2.2 - local Wi-Fi multiplayer (lockstep).
//
// Every phone runs the same simulation. The host's hero is the game's "player" on every phone, the
// other humans' heroes are computer heroes without AI that are driven by commands. Local touches
// become commands for frame F+INPUT_DELAY; the host collects everybody's commands for a frame and
// sends one bundle; a phone only simulates frame F once it has bundle F (fixed dt, virtual clock,
// shared random numbers), so all phones stay identical. Camera and HUD follow the phone's own hero.
#include <cstdint>
#include <string>
#include <vector>

class CharacterBase;
class GameLayer;
namespace cocos2d
{
	struct cc_timeval;
}

namespace mp
{
	enum Cmd : uint8_t
	{
		CmdWalk = 1,	// a = x*10000, b = y*10000
		CmdIdle,		// joystick released
		CmdAttack,		// a = ABType
		CmdRelease,		// normal attack button released
		CmdUseGear,		// a = GearType
		CmdBuyGear,		// a = GearType
	};

	struct LineupEntry
	{
		std::string name;
		uint8_t group; // 0 Konoha, 1 Akatsuki
		int8_t owner;  // player id, -1 = bot
	};

	// session state
	bool active();	 // a room is open / joined
	bool inBattle(); // lockstep battle running (fixed dt, shared RNG)
	bool isHost();
	bool isClient();
	int myId();

	// random numbers used by the game logic (Defines.h macros)
	int rngRandom(int x);
	void rngSetRand();
	int logicRand();

	// engine hooks (CCDirector / CCTime)
	bool stepGate();
	void afterStep();
	bool catchUp(); // a client behind the host may run extra frames now
	bool virtualTime(cocos2d::cc_timeval *tv);
	void appPaused(bool paused);

	// select screen: returns true while the phone waits for the host's line-up
	bool requestStart(const char *hero);
	bool lineupReady();
	void applyLineupToMode(); // sets the host's game mode on this phone
	bool hasLineup();
	const std::vector<LineupEntry> &lineup();
	uint8_t hostGroup();

	// battle
	void battlePrepare();				 // LoadLayer::onLoadFinish, before the battle objects exist
	void battleHeroesCreated(GameLayer *gl); // after GameLayer::initHeros
	void battleOver();
	bool isRemoteHuman(CharacterBase *c); // a human's hero that must not run AI
	CharacterBase *myHero();

	// local input (GameLayer / HUD)
	void localWalk(float x, float y);
	void localCmd(Cmd c, int a = 0);
	bool attackReleased(CharacterBase *c); // per-hero "normal attack button up"

	// UI
	std::string status();
	std::string busy();
	void configure(int role, const char *ip); // 0 off, 1 host, 2 client (ally), 4 client (rival)
	void setTeam(int team);
	int team();
	void openLobby(); // Java lobby
} // namespace mp
