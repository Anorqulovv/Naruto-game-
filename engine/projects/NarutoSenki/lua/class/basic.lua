--[[--
	Basic Types
]]

Team = {
    Akatsuki    = 'Akatsuki',
    Konoha      = 'Konoha'
}

local _None = 'None'

ns.CharactersLayout = {
    -- Page One
    -- {
        'Naruto',		'Sakura',		'Sai',			'Kakashi', --[[ Right ]] _None,		    _None,	 	    _None,
        'Shikamaru',	'Ino', 			'Choji',		'Asuma',   --[[ Right ]] 'Kiba', 	    'Hinata', 	    'Shino',
        'Neji', 		'Tenten', 		'Lee', 			_None,     --[[ Right ]] _None,         _None, 	        _None,
    -- },
    -- Page Two
    -- {
        _None, 		    'Tobirama',		'Hiruzen', 		'Minato',   --[[ Right ]] 'Jiraiya', 	'Tsunade', 		'Orochimaru',
        'Gaara',		_None,	 		'Kankuro',	 	'Chiyo',    --[[ Right ]] _None,        _None,          _None,
        'Sasuke', 		'Karin', 		'Suigetsu', 	'Jugo',     --[[ Right ]] _None,        _None,          _None,
    -- },
    -- Page Three
    -- {
        _None, 		   'Tobi', 		    'Konan',		_None,      --[[ Right ]] 'Pain',        _None,         _None,
        _None, 		    'Deidara', 		'Kakuzu', 		'Hidan',    --[[ Right ]] 'Kimimaro',    _None,         _None,
        'Itachi', 		'Kisame',		_None, 		    _None,      --[[ Right ]] _None, 		 _None,         _None,
        -- },
    -- Page Four
    -- {
        -- _None,			_None,			_None,			_None,      --[[ Right ]] _None,		_None,		    _None,
        -- _None,			_None,			_None,			_None,      --[[ Right ]] _None,		_None,		    _None,
        -- _None,			_None,			_None,			_None,      --[[ Right ]] _None,		_None,		    _None,
    -- },
}

-- RotN 2.2: Rise of the Ninja's extra heroes (second page of the select screen)
ns.RotnHeroes = {
    'KillerBee', 'Madara', 'Hashirama', 'Izuna', 'Obito',
    'Kaguya', 'RikudoSennin', 'NarutoKCM', 'Shisui', 'Zabuza', 'Sasori', 'Onoki',
    'Mei', 'KazekageGaara', 'Temari', 'Hanzo', 'Yagura', 'ZetsuSpiral',
}
