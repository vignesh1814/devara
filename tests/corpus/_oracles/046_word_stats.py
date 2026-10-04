from _rt import *
s = sys.stdin.readline().rstrip("\n")
words = s.replace("\t", " ").split()
best = max(words, key=lambda w: len(w))  # first longest
out(len(words)); out(len(best)); out(best)
