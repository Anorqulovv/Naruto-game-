#pragma once
// RotN 2.2: Rise of the Ninja's extra heroes. Each one fights with the skills of a V2 hero (its class and
// timings) but has its own sprites, pictures and voices (Unit/Ninja/<Base>/<Skin>.xml, <Skin>_*.png, Audio/<Skin>).
#include <string>

struct HeroSkin
{
	const char *skin;
	const char *base;
};

constexpr HeroSkin kHeroSkins[] = {
	{"KillerBee", "Sakura"},
	{"Madara", "Pain"},
	{"Hashirama", "Gaara"},
	{"Izuna", "Choji"},
	{"ZetsuSpiral", "Hidan"},
	{"KazekageGaara", "Hinata"},
	{"Obito", "Jugo"},
	{"Sasori", "Kankuro"},
	{"Mei", "Karin"},
	{"JuubiObito", "Kimimaro"},
	{"Onoki", "Konan"},
	{"RikudoSennin", "Neji"},
	{"Zabuza", "Orochimaru"},
	{"Yagura", "Sai"},
	{"Hanzo", "Shikamaru"},
	{"Temari", "Shino"},
	{"Shisui", "Suigetsu"},
	{"ObitoMask", "Tenten"},
	{"Kaguya", "Tobi"},
	{"NarutoKCM", "Tsunade"},
};

inline const char *skinBase(const std::string &name)
{
	for (auto &s : kHeroSkins)
		if (name == s.skin)
			return s.base;
	return nullptr;
}
