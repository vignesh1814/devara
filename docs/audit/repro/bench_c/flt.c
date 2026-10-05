#include <stdio.h>
#include <stdint.h>
double integrate(int64_t n){double s=0,x,h=1.0/n; for(int64_t i=0;i<n;i++){x=(i+0.5)*h; s=s+4.0/(1.0+x*x);} return s*h;}
int main(){printf("%g\n",integrate(100000000));}
