#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
int main(){ int64_t n=30000000; bool *prime=calloc(n+1,1); int64_t i,p,j,count=0;
for(i=2;i<=n;i++) prime[i]=1;
for(p=2;p*p<=n;p++) if(prime[p]) for(j=p*p;j<=n;j+=p) prime[j]=0;
for(i=2;i<=n;i++) if(prime[i]) count++;
printf("%lld\n",(long long)count); free(prime);}
