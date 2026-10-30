obj-m += vt_abi_probe.o
obj-m += vt_touch.o

KDIR ?=
ARCH ?= arm64

.PHONY: all clean
all:
	@test -n "$(KDIR)" || (echo "Set KDIR to the matching prepared kernel build directory"; exit 1)
	@test -s "$(KDIR)/Module.symvers" || (echo "Matching Module.symvers is required"; exit 1)
	$(MAKE) -C "$(KDIR)" M="$(CURDIR)" ARCH="$(ARCH)" CROSS_COMPILE="$(CROSS_COMPILE)" modules

clean:
	@test -n "$(KDIR)"
	$(MAKE) -C "$(KDIR)" M="$(CURDIR)" clean
