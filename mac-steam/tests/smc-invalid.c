// Invalid instructions on a hot SMC page must trap once, then run repaired code.
// Build on x86-64: gcc -O2 -static -o /tmp/smc-invalid tests/smc-invalid.c
// Run natively and under FEX with FEX_SMCHOTPAGEFAULTS=32 (and =0 as control).
#define _GNU_SOURCE
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <ucontext.h>
#include <unistd.h>

static volatile unsigned char *page;
static volatile sig_atomic_t faults, bad_frame, mode;

static void repair(int sig, siginfo_t *info, void *context) {
    ucontext_t *uc = context;
    if (++faults > 4) _exit(20); // Repeated stale invalid-opcode translations.
    if (sig != SIGILL || info->si_code != ILL_ILLOPN ||
        info->si_addr != (void *)page ||
        uc->uc_mcontext.gregs[REG_RIP] != (greg_t)page ||
        uc->uc_mcontext.gregs[REG_TRAPNO] != 6)
        bad_frame = 1;
    if (mode == 0) page[0] = 0x90; // Invalid 64-bit PUSH SS -> NOP.
    else page[1] = 0x1f; // 0f 04 c0 -> NOP; first byte remains unchanged.
}

int main(void) {
    alarm(10);
    struct sigaction sa = {.sa_sigaction = repair, .sa_flags = SA_SIGINFO};
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGILL, &sa, NULL)) return 2;
    for (mode = 0; mode < 2; ++mode) {
        page = mmap(NULL, 4096, PROT_READ | PROT_WRITE | PROT_EXEC,
                    MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (page == MAP_FAILED) return 3;
        const unsigned char get[] = {0xb8, 7, 0, 0, 0, 0xc3};
        memcpy((void *)(page + 64), get, sizeof(get));
        // Make this page hot before executing the invalid instruction.
        for (int i = 0; i < 100; ++i) {
            page[128] = i;
            if (((int (*)(void))(page + 64))() != 7) return 4;
        }
        if (mode == 0) {
            page[0] = 0x16;
            memcpy((void *)(page + 1), get, sizeof(get));
        } else {
            page[0] = 0x0f; page[1] = 0x04; page[2] = 0xc0;
            memcpy((void *)(page + 3), get, sizeof(get));
        }
        faults = bad_frame = 0;
        int value = ((int (*)(void))page)();
        printf("mode=%d value=%d faults=%d bad_frame=%d\n",
               mode, value, faults, bad_frame);
        if (value != 7 || faults != 1 || bad_frame) return 5;
        munmap((void *)page, 4096);
    }
    puts("RESULT: PASS");
    return 0;
}
