--
-- SelectLayer
--
function SelectLayer:init()
    log('Initial SelectLayer...')

    self.mode = _G.mode
    self.enableCustomSelect = _G.enableCustomSelect
    if self.mode == GameMode.Clone or self.mode == GameMode.OneVsOne then
        self.enableCustomSelect = false
        self.is3v3Mode = false
        self.is4v4Mode = false
    else
        self.is3v3Mode = self.mode == GameMode.Classic or self.mode ==
                             GameMode.RandomDeathmatch
        -- RotN 2.2: the FourVsFour slot is the 2 VS 2 mode (one ally to choose)
        self.is2v2Mode = self.mode == GameMode.FourVsFour
        self.is4v4Mode = self.mode == GameMode.HardCore_4Vs4
    end
    self.enableHardCore = false

    self.pageNum = 2 -- RotN 2.2: page 1 V2 heroes, page 2 Rise of the Ninja heroes

    self._comLabel1 = nil
    self._comLabel2 = nil
    self._comLabel3 = nil
    self._com1Select = nil
    self._com2Select = nil
    self._com3Select = nil

    self._heroName = nil
    self._heroHalfImage = nil

    self.pageLayers = {}
    self.pageButtons = {}

    self._playerSelect = nil
    self.selectHero = nil

    tools.addSprites('Record.plist', 'Record2.plist', 'Select.plist',
                     'UI.plist', 'Report.plist', 'Ougis.plist', 'Ougis2.plist',
                     'Map.plist', 'Gears.plist')

    -- if CC_TARGET_PLATFORM == CC_PLATFORM_ANDROID then
    -- if not KTools:checkMD5() then
    -- 	SimpleAudioEngine:sharedEngine():stopBackgroundMusic()
    -- 	CCDirector:sharedDirector():end()
    -- 	return false
    -- end
    -- end

    local width, height = display.width, display.height

    local bg_src = self.enableCustomSelect and 'red_bg.png' or 'blue_bg.png'
    local bgSprite = display.newSprite(bg_src, 0, 0)
    bgSprite:setAnchorPoint(0, 0)
    bgSprite:fullScreen()
    self:addChild(bgSprite, -5)

    -- RotN 2.2: only the ink background, no V2 clouds/gold frames

    local select_title = display.newSprite('#select_title.png')
    if select_title:getContentSize().width >= 560 then select_title:setScaleX(display.width / select_title:getContentSize().width) end
    select_title:setAnchorPoint(0, 0)
    select_title:setPosition(2,
                             height - select_title:getContentSize().height - 2)
    self:addChild(select_title, 3)

    local selectNameList = {}
    local selectButtons = {}

    for i = 1, self.pageNum do
        -- initial page list
        local index = i
        local pageLayer = TouchGroup:create() -- display.newLayer()
        local page_btn = ui.newImageMenuItem({
            image = '#page' .. tostring(i) .. '_off.png',
            imageSelected = '#page' .. tostring(i) .. '_on.png',
            listener = function()
                return self:onPageButtonClick(index)
            end
        })

        self:addChild(pageLayer, 5)
        if i == 1 then
            pageLayer:show()
            page_btn:selected()
        else
            pageLayer:hide()
            pageLayer:setPositionY(2000)
        end

        table.insert(self.pageLayers, pageLayer)
        table.insert(self.pageButtons, page_btn)
    end

    -- RotN 2.2: RotN cards in a slanted block on the right (like Rise of the Ninja)
    -- a hero is shown only if all its select pictures exist (a missing picture would crash the game)
    local cache = CCSpriteFrameCache:sharedSpriteFrameCache()
    local function hasPictures(name)
        for _, suffix in ipairs({'_rcard.png', '_shadow.png', '_font.png', '_small.png'}) do
            if not cache:spriteFrameByName(name .. suffix) then
                log('Select: skip %s (no %s)', name, suffix)
                return false
            end
        end
        return true
    end
    local pages = {{}, {}}
    for _, name in ipairs(ns.CharactersLayout) do
        if name ~= SelectButton.Char_None and name ~= SelectButton.Char_None2 and hasPictures(name) then
            pages[1][#pages[1] + 1] = name
        end
    end
    for _, name in ipairs(ns.RotnHeroes) do
        if hasPictures(name) then pages[2][#pages[2] + 1] = name end
    end
    local perRow, cardScale = 9, 0.86
    local cardW, rowH, slant = 26, 60, 20
    self.cardScale = cardScale

    for page, charactersList in ipairs(pages) do
    for i = 1, #charactersList do
        local charName = charactersList[i]
        selectNameList[#selectNameList + 1] = charName

        local idx = i - 1
        local Column = idx % perRow
        local Row = toint(idx / perRow)

        local select_btn = SelectButton:create(charName .. '_rcard.png')
        select_btn:setScale(cardScale)
        select_btn._selectLayer = self
        select_btn._charName = charName
        local right = width - 12 - Row * slant
        select_btn:setPosition(CCPoint(right - (perRow - Column) * cardW,
                                       height - 70 - Row * rowH))
        self.pageLayers[page]:addWidget(select_btn)
        selectButtons[#selectButtons + 1] = select_btn
    end
    end

    local page_menu = ui.newMenu(self.pageButtons)
    page_menu:alignItemsVerticallyWithPadding(10)
    page_menu:setPosition(width - perRow * cardW - 4 * slant - 44, 70)
    self:addChild(page_menu, 10)

    self.selectButtons = selectButtons
    self.selectNameList = selectNameList
    self:setSelectList(table.toCCArray(selectNameList))

    local hero = selectNameList[1]
    if hero then
        local heroHalfImage = display.newSprite('#' .. hero .. '_shadow.png', 0, 0)
        heroHalfImage:setAnchorPoint(0, 0)
        self:addChild(heroHalfImage, 1)

        -- the RotN shadow already carries the name
        local heroName = display.newSprite('#' .. hero .. '_font.png', 100, 20)
        heroName:setAnchorPoint(0.5, 0)
        heroName:setVisible(false)
        self:addChild(heroName, 5)

        self._heroName = heroName
        self._heroHalfImage = heroHalfImage
    end

    local selectBtn = selectButtons[1]
    local selectImg = display.newSprite('#1p.png', selectBtn:getPositionX() - 2,
                                        selectBtn:getPositionY() - 2)
    selectImg:setAnchorPoint(0, 0)
    selectImg:setScaleX((29 * self.cardScale + 4) / selectImg:getContentSize().width)
    selectImg:setScaleY((66 * self.cardScale + 4) / selectImg:getContentSize().height)
    self:addChild(selectImg, 500)
    local blink = CCBlink:create(0.6, 1)
    selectImg:runAction(CCRepeatForever:create(blink))
    self._selectImg = selectImg
    self.selectHero = selectBtn._charName

    if self.enableCustomSelect then
        if self.is2v2Mode or self.is3v3Mode or self.is4v4Mode then
            self:initCustomSelectMode()
        end
    end

    local ranking_btn = ui.newImageMenuItem({
        image = '#ranking_btn.png',
        listener = handler(self, SelectLayer.onRankingButtonClick)
    })
    ranking_btn:setAnchorPoint(1, 0.5)
    local menu3 = ui.newMenu({ranking_btn})
    menu3:setPosition(width - 15, height - 34)
    menu3:setVisible(false) -- RotN 2.2: no online ranking
    self:addChild(menu3, 5)

    local start_btn = ui.newImageMenuItem({
        image = '#rotn_start_btn.png',
        -- call c++ layer function
        listener = function() self:onGameStart() end
    })
    local menu = ui.newMenu({start_btn})
    menu:setAnchorPoint(0, 0)
    menu:setPosition(width - 52, 26)
    self:addChild(menu, 5)

    -- RotN 2.2: undo the last pick (own hero or a computer ally) and choose again
    local cancel_btn = ui.newTTFLabelMenuItem({
        text = 'BEKOR QILISH',
        size = 12,
        color = ccc3(255, 236, 200),
        align = ui.TEXT_ALIGN_CENTER,
        dimensions = CCSizeMake(100, 26),
    })
    -- (ui.newTTFLabelMenuItem binds its listener to node events, not to taps)
    cancel_btn:registerScriptTapHandler(function() self:cancelSelect() end)
    local cancelBg = CCLayerColor:create(ccc4(0, 0, 0, 150), 100, 26)
    cancelBg:setPosition(width - 180, 13)
    self:addChild(cancelBg, 4)
    local cancelMenu = ui.newMenu({cancel_btn})
    cancelMenu:setPosition(width - 130, 26)
    self:addChild(cancelMenu, 5)
    lockStack = {}

    local skill_btn = ui.newImageMenuItem({
        image = '#rotn_skill_btn.png',
        listener = handler(self, SelectLayer.onSkillMenuButtonClick)
    })
    local menu2 = ui.newMenu({skill_btn})
    menu2:setAnchorPoint(0, 0)
    menu2:setPosition(width - 42, 62)
    self:addChild(menu2, 5)

    -- Desktop return button
    if _G.platform == 'desktop' then
        local skill_btn = ui.newImageMenuItem({
            image = '#return_btn.png',
            listener = backToStartMenu
        })
        local menu3 = ui.newMenu({skill_btn})
        menu3:setAnchorPoint(0, 0)
        menu3:setPosition(width - 35, 135)
        self:addChild(menu3, 5)
    end

    if save.isBGM() then audio.playMusic(ns.music.SELECT_MUSIC, true) end
end

function SelectLayer:initCustomSelectMode()
    log('Initial Custom Select Mode...')
    local teamSelector = display.newLayer()
    -- local uiLayer = TouchGroup:create()
    -- teamSelector:addChild(uiLayer, 5)

    -- local hardcore_switch_btn = CheckBox:create()
    -- hardcore_switch_btn:loadTextures( -- load textures
    -- "check_bg.png", "check_bg.png", "check.png", "", "", ns.UITexType.Local)
    -- -- "", -- backGround
    -- -- "", -- backGroundSelected
    -- -- "", -- cross
    -- -- "", -- backGroundDisabled
    -- -- "", -- frontCrossDisabled
    -- -- ns.UITexType.Plist)
    -- hardcore_switch_btn:setPosition(
    --     CCPoint(text:getContentSize().width + 5, 260))
    -- hardcore_switch_btn:setScale(0.4)
    -- hardcore_switch_btn:addEventListenerCheckBox(
    --     function(_, event)
    --         self.enableHardCore = event == ns.CheckBoxEventType.selected
    --         -- log('Is enable hardcore [ %s ]', tostring(self.enableHardCore))
    --     end)
    -- uiLayer:addWidget(hardcore_switch_btn)

    local teamBg = display.newSprite('#team_bg.png', 0, 185)
    teamBg:setAnchorPoint(0, 0)
    teamSelector:addChild(teamBg)

    -- init com selector 1
    local comSelector1 = display.newSprite('#unknow_select.png', 2, 194)
    comSelector1:setAnchorPoint(0, 0)
    teamSelector:addChild(comSelector1)
    self._comSelector1 = comSelector1

    self._comLabel1 = display.newSprite('#com_label.png')
    self._comLabel1:setPosition(comSelector1:getPositionX() +
                                    comSelector1:getContentSize().width + 2 + 18,
                                comSelector1:getPositionY() +
                                    comSelector1:getContentSize().height / 2)
    teamSelector:addChild(self._comLabel1)

    if self.is2v2Mode then
        teamSelector:setPositionY(-180)
        self:addChild(teamSelector, 50)
        return
    end

    -- init com selector 2
    local comSelector2 = display.newSprite('#unknow_select.png')
    comSelector2:setAnchorPoint(0, 0)
    comSelector2:setPosition(comSelector1:getPositionX() +
                                 comSelector1:getContentSize().width + 40,
                             comSelector1:getPositionY())
    teamSelector:addChild(comSelector2)

    self._comLabel2 = display.newSprite('#com_label.png')
    self._comLabel2:setPosition(comSelector2:getPositionX() +
                                    comSelector2:getContentSize().width + 2 + 18,
                                comSelector2:getPositionY() +
                                    comSelector2:getContentSize().height / 2)
    teamSelector:addChild(self._comLabel2)
    self._comSelector2 = comSelector2

    -- init com selector 3
    if self.is4v4Mode then
        local comSelector3 = display.newSprite('#unknow_select.png')
        comSelector3:setAnchorPoint(0, 0)
        comSelector3:setPosition(comSelector2:getPositionX() +
                                     comSelector2:getContentSize().width + 40,
                                 comSelector2:getPositionY())
        teamSelector:addChild(comSelector3)

        self._comLabel3 = display.newSprite('#com_label.png')
        self._comLabel3:setPosition(comSelector3:getPositionX() +
                                        comSelector3:getContentSize().width + 3 +
                                        18, comSelector3:getPositionY() +
                                        comSelector3:getContentSize().height / 3)
        teamSelector:addChild(self._comLabel3)
        self._comSelector3 = comSelector3
    end

    teamSelector:setPositionY(-180) -- RotN 2.2: ally picks sit in the bottom-left corner
    self:addChild(teamSelector, 50)
end

function SelectLayer:onQuestBtn()
    -- not support
    self:setTip('ComingSoon')
end

function SelectLayer:onRankingButtonClick()
    -- not support
    self:setTip('ComingSoon')
end

function SelectLayer:onSkillMenuButtonClick()
    local scene = CCScene:create()
    local skillLayer = SkillLayer:create(self)
    scene:addChild(skillLayer)

    director.pushScene(scene)
end

function SelectLayer:onPageButtonClick(index)
    audio.playSound(ns.menu.SELECT_SOUND)

    for i, pageBtn in pairs(self.pageButtons) do
        if i == index then
            pageBtn:selected()
        else
            pageBtn:unselected()
        end
    end
    for i, pageLayer in pairs(self.pageLayers) do
        if i == index then
            pageLayer:show()
            pageLayer:setPositionY(0)
        else
            pageLayer:hide()
            pageLayer:setPositionY(10000)
        end
    end
end

function SelectLayer:setSelected(btn)
    if self._selectImg then
        self._selectImg:setPosition(CCPoint(btn:getPositionX() - 2,
                                            btn:getPositionY() - 2))
    end

    if not self.enableCustomSelect and self._playerSelect then return end

    self.selectHero = btn._charName

    local fd = CCFadeOut:create(1.0)
    local seq = CCRepeatForever:create(transition.sequence({fd, fd:reverse()}))

    if not self._playerSelect then
        if btn._clickTime >= 2 then
            self:setSelectHero(btn._charName)
            self._playerSelect = self.selectHero
            self:pushLock(btn, 'player')

            if not self.enableCustomSelect then
                self._selectImg:removeFromParent()
                self._selectImg = nil
            else
                if self._comLabel1 then
                    self._comLabel1:runAction(seq)
                end
            end
        end

        self._heroHalfImage:removeFromParent()
        local charName = '#' .. btn._charName

        self._heroHalfImage = display.newSprite(charName .. '_shadow.png', 0, 0)
        self._heroHalfImage:setAnchorPoint(CCPoint(0, 0))
        self:addChild(self._heroHalfImage, 1)

        self._heroName:removeFromParent()
        self._heroName = display.newSprite(charName .. '_font.png', 100, 20)
        self._heroName:setAnchorPoint(CCPoint(0.5, 0))
        self._heroName:setVisible(false)
        self:addChild(self._heroName, 5)
    elseif not self._com1Select then
        self._comSelector1:setDisplayFrame(
            display.newSpriteFrame(self.selectHero .. '_small.png'))

        if btn._clickTime >= 2 then
            self._com1Select = self.selectHero
            self:setCom1Select(self._com1Select)
            self:pushLock(btn, 'com1')

            self._comLabel1:stopAllActions()
            self._comLabel1:setOpacity(255)
            self._comLabel1:setDisplayFrame(
                display.newSpriteFrame('com_label2.png'))

            if self.is2v2Mode and self._selectImg then
                self._selectImg:removeFromParent()
                self._selectImg = nil
            end
        end
    elseif not self._com2Select then
        self._comSelector2:setDisplayFrame(
            display.newSpriteFrame(self.selectHero .. '_small.png'))

        if btn._clickTime >= 2 then
            self._com2Select = self.selectHero
            self:setCom2Select(self._com2Select)
            self:pushLock(btn, 'com2')

            self._comLabel2:stopAllActions()
            self._comLabel2:setOpacity(255)
            self._comLabel2:setDisplayFrame(
                display.newSpriteFrame('com_label2.png'))
        end
    elseif not self._com3Select then
        self._comSelector3:setDisplayFrame(
            display.newSpriteFrame(self.selectHero .. '_small.png'))

        if btn._clickTime >= 2 then
            self._com3Select = self.selectHero
            self:setCom3Select(self._com3Select)
            self:pushLock(btn, 'com3')

            self._comLabel3:stopAllActions()
            self._comLabel3:setOpacity(255)
            self._comLabel3:setDisplayFrame(
                display.newSpriteFrame('com_label2.png'))

            self._selectImg:removeFromParent()
            self._selectImg = nil
        end
    end
end

-- picks made on the select screen, newest last (undone by "BEKOR QILISH")
lockStack = {}

function SelectLayer:pushLock(btn, kind)
    lockStack[#lockStack + 1] = {btn = btn, kind = kind}
end

function SelectLayer:cancelSelect()
    local top = table.remove(lockStack)
    if not top then return end
    audio.playSound('Audio/Menu/cancel.ogg')
    local btn = top.btn
    if btn._black then
        btn._black:removeFromParent()
        btn._black = nil
    end
    btn._isAviable = true
    for _, b in pairs(self.selectButtons) do b._clickTime = 0 end

    local function waiting(label, selector)
        if selector then
            selector:setDisplayFrame(display.newSpriteFrame('unknow_select.png'))
        end
        if label then
            label:stopAllActions()
            label:setOpacity(255)
            label:setDisplayFrame(display.newSpriteFrame('com_label.png'))
        end
    end
    if top.kind == 'player' then
        self._playerSelect = nil
        self:setSelectHero(nil)
        waiting(self._comLabel1, nil)
    elseif top.kind == 'com1' then
        self._com1Select = nil
        self:setCom1Select(nil)
        waiting(self._comLabel1, self._comSelector1)
        waiting(self._comLabel2, nil)
    elseif top.kind == 'com2' then
        self._com2Select = nil
        self:setCom2Select(nil)
        waiting(self._comLabel2, self._comSelector2)
        waiting(self._comLabel3, nil)
    elseif top.kind == 'com3' then
        self._com3Select = nil
        self:setCom3Select(nil)
        waiting(self._comLabel3, self._comSelector3)
    end
    -- the label of the slot that is being chosen now blinks again
    local next = (top.kind == 'player' and self._comLabel1 and nil) or
                 (top.kind == 'com1' and self._comLabel1) or
                 (top.kind == 'com2' and self._comLabel2) or
                 (top.kind == 'com3' and self._comLabel3)
    if next then
        local fd = CCFadeOut:create(1.0)
        next:runAction(CCRepeatForever:create(transition.sequence({fd, fd:reverse()})))
    end

    if not self._selectImg then
        local selectImg = display.newSprite('#1p.png', btn:getPositionX() - 2, btn:getPositionY() - 2)
        selectImg:setAnchorPoint(0, 0)
        selectImg:setScaleX((29 * self.cardScale + 4) / selectImg:getContentSize().width)
        selectImg:setScaleY((66 * self.cardScale + 4) / selectImg:getContentSize().height)
        self:addChild(selectImg, 500)
        selectImg:runAction(CCRepeatForever:create(CCBlink:create(0.6, 1)))
        self._selectImg = selectImg
    end
    self.selectHero = btn._charName
end

function SelectLayer:noComSelect()
    if self.is4v4Mode then
        return self._com3Select
    elseif self.is3v3Mode then
        return self._com2Select
    elseif self.is2v2Mode then
        return self._com1Select
    else
        return self._playerSelect
    end
end

function backToStartMenu()
    log('back to main menu')

    _G.mode = nil
    audio.playSound('Audio/Menu/cancel.ogg')
    local menuScene = CCScene:create()
    local menuLayer = StartMenu:create()

    hook.registerInitHandlerOnly(menuLayer)
    menuScene:addChild(menuLayer)
    director.replaceSceneWithFade(menuScene, 1)
end
