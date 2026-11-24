#pragma once
#include "GameMode/IGameModeHandler.hpp"

class Mode4v4 : public IGameModeHandler
{
public:
	void init()
	{
		// RotN 2.2: this slot (GameMode::FourVsFour) is the 2 VS 2 mode
		CCLOG("Enter 2 VS 2 mode.");

		gd.isHardCore = true;
	}

	void onInitHeros()
	{
		initHeros(2, 2);
	}

	void onGameStart()
	{
	}

	void onGameOver()
	{
	}

	void onCharacterInit(CharacterBase *c)
	{
	}

	void onCharacterDead(CharacterBase *c)
	{
	}

	void onCharacterReborn(CharacterBase *c)
	{
	}
};
