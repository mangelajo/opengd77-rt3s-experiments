/*
 * Copyright (C) 2026 Miguel Angel Ajo Pelayo, EA4IPW
 *
 * Redistribution and use in source and binary forms, with or without modification,
 * are permitted under the terms of the OpenGD77 modified BSD-3-Clause license,
 * non-commercial only — see the project licence for full text.
 */
#include "functions/codeplug.h"
#include "user_interface/uiGlobals.h"
#include "user_interface/menuSystem.h"
#include "user_interface/uiLocalisation.h"
#include "user_interface/uiUtilities.h"

//
// "Reset custom data" — format the OpenGD77 custom-data flash region.
//
// This wipes the 64 KB region at SPI flash FLASH_ADDRESS_OFFSET that stores
// themes / boot image / custom beep / satellite TLE, and re-writes the
// "OpenGD77" signature so subsequent custom-data writes from the firmware (or
// from external CPS tools) work. It is needed on radios codeplugged exclusively
// via tools that don't initialise this region (e.g. qdmr).
//
// Destructive, so confirmation mirrors the existing Calibration Factory Reset
// pattern: plain GREEN does nothing; SK2 + GREEN actually runs the format.
//

static void updateScreen(void);
static void handleEvent(uiEvent_t *ev);

menuStatus_t menuResetCustomData(uiEvent_t *ev, bool isFirstRun)
{
	if (isFirstRun)
	{
		menuDataGlobal.numItems = 0;

		voicePromptsInit();
		voicePromptsAppendPrompt(PROMPT_SILENCE);
		voicePromptsAppendLanguageString(currentLanguage->reset_configuration);
		voicePromptsAppendPrompt(PROMPT_SILENCE);
		promptsPlayNotAfterTx();

		updateScreen();
		return MENU_STATUS_SUCCESS;
	}

	if (ev->hasEvent)
	{
		handleEvent(ev);
	}
	return MENU_STATUS_SUCCESS;
}

static void updateScreen(void)
{
	displayClearBuf();
	menuDisplayTitle(currentLanguage->reset_configuration);

	// Layout mirrors the simple two-line confirmation pattern used by other
	// destructive screens: a "what it does" reminder above the "how to confirm"
	// hint. Literal English — not worth a per-language string for a recovery
	// action a typical user invokes at most once.
	displayPrintCentered(20, "Wipe themes,",         FONT_SIZE_3);
	displayPrintCentered(36, "boot img, beep, TLE",  FONT_SIZE_1);
	displayPrintCentered(54, "SK2 + GREEN to OK",    FONT_SIZE_3);

	displayRender();
}

static void handleEvent(uiEvent_t *ev)
{
	if (ev->events & BUTTON_EVENT)
	{
		if (repeatVoicePromptOnSK1(ev))
		{
			return;
		}
	}

	if ((ev->events & FUNCTION_EVENT) && (ev->function == FUNC_REDRAW))
	{
		updateScreen();
		return;
	}

	if (ev->events & KEY_EVENT)
	{
		if (KEYCHECK_SHORTUP(ev->keys, KEY_RED))
		{
			menuSystemPopPreviousMenu();
			return;
		}

		if (KEYCHECK_SHORTUP(ev->keys, KEY_GREEN))
		{
			if (BUTTONCHECK_DOWN(ev, BUTTON_SK2))
			{
				bool ok = codeplugResetOpenGD77CustomDataArea();

				uiNotificationShow(NOTIFICATION_TYPE_MESSAGE, NOTIFICATION_ID_MESSAGE, 2500,
						(ok ? "Storage reset" : "Reset failed"), false);

				menuSystemPopPreviousMenu();
				return;
			}
			// Plain GREEN: ignore — require SK2 to confirm.
		}
	}
}
