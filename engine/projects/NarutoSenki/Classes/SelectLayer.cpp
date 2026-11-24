#include "Mp/Mp.h"
#include <time.h>
#include "StartMenu.h"
#include "Constants/UiFlowKeys.hpp"

#if (CC_TARGET_PLATFORM == CC_PLATFORM_ANDROID)
#include <jni.h>
#include "../../../cocos2dx/platform/android/jni/JniHelper.h"
#endif

SelectLayer::~SelectLayer()
{
	CC_SAFE_RELEASE(_selectList);

	auto handler = getGameModeHandler();
	handler->selectLayer = nullptr;
	if (!isStart)
		handler->resetCheats();
}

void SelectLayer::onGameStart()
{
	if (isStart || mpWaiting)
		return;

	// Wi-Fi room: tell the host my hero and wait for its line-up
	if (!mpReady && mp::requestStart(_playerSelect))
	{
		mpWaiting = true;
		setKeypadEnabled(false);
		schedule(schedule_selector(SelectLayer::mpWaitLineup), 0.1f);
		return;
	}
	isStart = true;

	setKeypadEnabled(false);

	SimpleAudioEngine::sharedEngine()->stopBackgroundMusic(true);
	SimpleAudioEngine::sharedEngine()->playEffect("Audio/Menu/confirm.ogg");

	Scene *loadScene = Scene::create();
	LoadLayer *loadLayer = LoadLayer::create();

	auto gameModeHandler = getGameModeHandler();
	gameModeHandler->selectLayer = this;
	gameModeHandler->onInitHeros();
	loadLayer->preloadAudio();
	loadScene->addChild(loadLayer);

	Director::sharedDirector()->replaceScene(TransitionFade::create(1.25f, loadScene));
}

void SelectLayer::mpWaitLineup(float dt)
{
	if (!mp::lineupReady())
		return;
	unschedule(schedule_selector(SelectLayer::mpWaitLineup));
	mpWaiting = false;
	mpReady = true;
	mp::applyLineupToMode(); // the host's mode and team size
	onGameStart();
}

void SelectLayer::onExitTransitionDidStart()
{
	Layer::onExitTransitionDidStart();
	setKeypadEnabled(false);
}

void SelectLayer::onEnterTransitionDidFinish()
{
	Layer::onEnterTransitionDidFinish();
	setKeypadEnabled(true);
}

void SelectLayer::keyBackClicked()
{
	setKeypadEnabled(false);

	lua_call_func(UiFlowKeys::kBackToStartMenu);
}
