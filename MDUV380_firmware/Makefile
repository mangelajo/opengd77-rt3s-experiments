# OpenGD77 MDUV380 firmware build
# Reconstructed from .cproject (STM32CubeIDE managed build)

TARGET    := MDUV380_FW
BUILD_DIR := build

# --- toolchain ---------------------------------------------------------------
CROSS    := arm-none-eabi-
CC       := $(CROSS)gcc
AS       := $(CROSS)gcc -x assembler-with-cpp
LD       := $(CROSS)gcc
OBJCOPY  := $(CROSS)objcopy
SIZE     := $(CROSS)size

# --- MCU / arch flags --------------------------------------------------------
MCU_FLAGS := -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard

# --- preprocessor ------------------------------------------------------------
DEFS := \
    -DUSE_HAL_DRIVER \
    -DSTM32F405xx \
    -DPLATFORM_MDUV380

# Optional language pack (uncomment one to bake a default language)
# DEFS += -DLANGUAGE_BUILD_JAPANESE

# GITVERSION matches what STM32CubeIDE injects in .cproject
GITVERSION := $(shell git -C $(CURDIR) rev-parse --short HEAD 2>/dev/null || echo UNKNOWN)
DEFS += -DGITVERSION=\"$(GITVERSION)\"

INCLUDES := \
    -I. \
    -ICore/Inc \
    -Iapplication/include \
    -IUSB_DEVICE/Target \
    -IUSB_DEVICE/App \
    -IMiddlewares/Third_Party/FreeRTOS/Source/include \
    -IMiddlewares/Third_Party/FreeRTOS/Source/portable/GCC/ARM_CM4F \
    -IMiddlewares/Third_Party/FreeRTOS/Source/CMSIS_RTOS_V2 \
    -IMiddlewares/ST/STM32_USB_Device_Library/Core/Inc \
    -IMiddlewares/ST/STM32_USB_Device_Library/Class/CDC/Inc \
    -IDrivers/CMSIS/Include \
    -IDrivers/CMSIS/Device/ST/STM32F4xx/Include \
    -IDrivers/STM32F4xx_HAL_Driver/Inc \
    -IDrivers/STM32F4xx_HAL_Driver/Inc/Legacy

# --- compile flags -----------------------------------------------------------
COMMON_FLAGS := $(MCU_FLAGS) -Os -g3 -ffunction-sections -fdata-sections -Wall \
                -Wno-format -Wno-format-truncation -Wno-stringop-overflow \
                -fstack-usage --specs=nano.specs

CFLAGS   := $(COMMON_FLAGS) $(DEFS) $(INCLUDES) -std=gnu11 -MMD -MP
ASFLAGS  := $(COMMON_FLAGS) $(DEFS) -MMD -MP -Wa,-I,$(BUILD_DIR)
LDSCRIPT := STM32F405VGTX_FLASH.ld
LDFLAGS  := $(MCU_FLAGS) -T$(LDSCRIPT) --specs=nosys.specs --specs=nano.specs \
            -Wl,-Map=$(BUILD_DIR)/$(TARGET).map,--cref \
            -Wl,--gc-sections -static \
            -Wl,--start-group -lc -lm -Wl,--end-group

# --- sources -----------------------------------------------------------------
# Source roots from .cproject sourceEntries
SRC_ROOTS := SeggerRTT application Core Middlewares Drivers USB_DEVICE

C_SRCS := $(shell find $(SRC_ROOTS) -name '*.c')
# Exclusion from .cproject
C_SRCS := $(filter-out application/include/user_interface/languages/src/languages_builder.c,$(C_SRCS))

S_SRCS := $(shell find $(SRC_ROOTS) -name '*.s' -o -name '*.S')

OBJS := $(addprefix $(BUILD_DIR)/,$(C_SRCS:.c=.o) $(S_SRCS:.s=.o))
OBJS := $(OBJS:.S=.o)
DEPS := $(OBJS:.o=.d)

# --- targets -----------------------------------------------------------------
.PHONY: all clean prepare flash-bin

all: $(BUILD_DIR)/OpenMDUV380.bin

# Step 1: generate the codec placeholder before compilation
prepare:
	@cd application/source/linkerdata && ../../../tools/codec_cleaner.Linux -C

# Step 2: compile/link
$(BUILD_DIR)/$(TARGET).elf: prepare $(OBJS) $(LDSCRIPT)
	@echo "  LD    $@"
	@$(LD) $(OBJS) $(LDFLAGS) -o $@
	@$(SIZE) $@

# Step 3: ELF -> raw .bin
$(BUILD_DIR)/$(TARGET).bin: $(BUILD_DIR)/$(TARGET).elf
	@echo "  BIN   $@"
	@$(OBJCOPY) -O binary -S $< $@

# Step 4: codec_cleaner post-process -> OpenMDUV380.bin
$(BUILD_DIR)/OpenMDUV380.bin: $(BUILD_DIR)/$(TARGET).bin
	@echo "  CLEAN $@"
	@cd $(BUILD_DIR) && ../tools/codec_cleaner.Linux -i $(TARGET).bin -o OpenMDUV380.bin
	@ls -la $@

# pattern rules
$(BUILD_DIR)/%.o: %.c
	@mkdir -p $(dir $@)
	@echo "  CC    $<"
	@$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: %.s
	@mkdir -p $(dir $@)
	@echo "  AS    $<"
	@$(AS) $(ASFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: %.S
	@mkdir -p $(dir $@)
	@echo "  AS    $<"
	@$(AS) $(ASFLAGS) -c $< -o $@

clean:
	rm -rf $(BUILD_DIR)

# --- flash targets ----------------------------------------------------------
# Run these from the HOST (not via the podman build wrapper) — flashing needs
# direct USB access.  Put the radio in DFU mode first (power off, hold SK1,
# power on).
#
# Defaults assume the surrounding OpenGD77/ layout this fork was set up with;
# override on the command line, e.g.:
#     make flash LOADER=/path/to/opengd77_stm32_firmware_loader.py
#
# NOTE: this Makefile builds the firmware with -DPLATFORM_MDUV380.  The flash-*
# targets below only switch the upload cipher; running this binary on a
# non-MDUV380 radio family is unlikely to boot without rebuilding with the
# matching PLATFORM_* define.
LOADER       ?= ../../../tools/mduv380_tools/opengd77_stm32_firmware_loader.py
PYTHON       ?= ../../../.venv/bin/python
FIRMWARE_BIN := $(BUILD_DIR)/OpenMDUV380.bin

.PHONY: flash flash-mduv380 flash-md2017 flash-dm1701 flash-md380

flash: flash-mduv380

flash-mduv380 flash-md2017 flash-dm1701 flash-md380:
	@test -f $(FIRMWARE_BIN) || { echo "ERROR: $(FIRMWARE_BIN) missing — run build.sh first." >&2; exit 1; }
	$(PYTHON) $(LOADER) -m $(PLATFORM) -f $(FIRMWARE_BIN)

flash-mduv380: PLATFORM := MD-UV380
flash-md2017:  PLATFORM := MD-2017
flash-dm1701:  PLATFORM := DM-1701
flash-md380:   PLATFORM := MD-380

-include $(DEPS)
