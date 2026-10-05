#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
int main(){ int64_t n=400; int64_t (*a)[n]=calloc(n*n,8),(*b)[n]=calloc(n*n,8),(*c)[n]=calloc(n*n,8); int64_t i,j,k,s,check=0;
for(i=0;i<n;i++)for(j=0;j<n;j++){a[i][j]=(i*7+j*3)%10;b[i][j]=(i*5+j*11)%10;}
for(i=0;i<n;i++)for(j=0;j<n;j++){s=0;for(k=0;k<n;k++)s+=a[i][k]*b[k][j];c[i][j]=s;}
for(i=0;i<n;i++)for(j=0;j<n;j++)check=(check*31+c[i][j])%1000000007;
printf("%lld\n",(long long)check);}
