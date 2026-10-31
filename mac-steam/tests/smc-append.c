// Exercises repeated insertion of validation/failure blocks in long hot code.
// Compile for x86-64: gcc -O2 -static -o aoe-smc-append smc-append.c
#define _GNU_SOURCE
#include <sys/mman.h>
#include <time.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static double now(void) {
    struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;
}
int main(int argc,char **argv) {
    unsigned instructions=argc>1?atoi(argv[1]):1000,iterations=argc>2?atoi(argv[2]):100;
    if(instructions>1300 || !iterations)return 2;
    unsigned char *code=mmap(NULL,4096,PROT_READ|PROT_WRITE|PROT_EXEC,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if(code==MAP_FAILED)return 1;
    code[0]=0xb8;memset(code+1,0,4);
    for(unsigned i=0;i<instructions;++i)memcpy(code+5+i*3,"\x48\xff\xc0",3);
    code[5+instructions*3]=0xc3;
    unsigned (*fn)(void)=(void*)code;
    double start=now();
    for(unsigned i=0;i<iterations;++i) {
        memcpy(code+1,&i,4);
        unsigned result=fn();
        if(result!=i+instructions){printf("FAIL iteration=%u expected=%u actual=%u\n",i,i+instructions,result);return 1;}
    }
    printf("PASS instructions=%u iterations=%u seconds=%.6f\n",instructions,iterations,now()-start);
    munmap(code,4096);return 0;
}
