#pragma once
#include <string>
#include "Enums/HeroEnum.h"
#include "Data/Skins.h"

constexpr const char *kHeroList[] = {
	HeroEnum::Asuma,
	HeroEnum::Chiyo,
	HeroEnum::Choji,
	HeroEnum::Deidara,
	HeroEnum::Gaara,
	HeroEnum::Hidan,
	HeroEnum::Hinata,
	HeroEnum::Hiruzen,
	HeroEnum::Itachi,
	HeroEnum::Jiraiya,
	HeroEnum::Jugo,
	HeroEnum::Kakashi,
	HeroEnum::Kakuzu,
	HeroEnum::Kankuro,
	HeroEnum::Karin,
	HeroEnum::Kiba,
	HeroEnum::Kimimaro,
	HeroEnum::Kisame,
	HeroEnum::Konan,
	HeroEnum::Lee,
	HeroEnum::Minato,
	HeroEnum::Naruto,
	HeroEnum::Neji,
	HeroEnum::Ino,
	HeroEnum::Orochimaru,
	HeroEnum::Pain,
	HeroEnum::Sai,
	HeroEnum::Sakura,
	HeroEnum::Sasuke,
	HeroEnum::Shikamaru,
	HeroEnum::Shino,
	HeroEnum::Suigetsu,
	HeroEnum::Tenten,
	HeroEnum::Tobi,
	HeroEnum::Tobirama,
	HeroEnum::Tsunade,
	// RotN 2.2: transformation forms that can be picked as heroes of their own
	HeroEnum::SageNaruto,
	HeroEnum::RikudoNaruto,
	HeroEnum::Nagato,
	HeroEnum::ImmortalSasuke,
	HeroEnum::SageJiraiya,
	// RotN's extra heroes (see Data/Skins.h)
	"KillerBee",
	"Madara",
	"Hashirama",
	"Izuna",
	"ZetsuSpiral",
	"KazekageGaara",
	"Obito",
	"Sasori",
	"Mei",
	"JuubiObito",
	"Onoki",
	"RikudoSennin",
	"Zabuza",
	"Yagura",
	"Hanzo",
	"Temari",
	"Shisui",
	"ObitoMask",
	"Kaguya",
	"NarutoKCM",
};

constexpr size_t kHeroNum =  std::size(kHeroList);

// A form and its base hero share one class and turn into each other in battle, so a battle may
// contain only one hero of each family.
inline std::string heroFamily(const std::string &name)
{
	if (auto base = skinBase(name))
		return heroFamily(base);
	if (name == "SageNaruto" || name == "RikudoNaruto")
		return "Naruto";
	if (name == "Nagato")
		return "Pain";
	if (name == "ImmortalSasuke")
		return "Sasuke";
	if (name == "SageJiraiya")
		return "Jiraiya";
	if (name == "RockLee")
		return "Lee";
	return name;
}
