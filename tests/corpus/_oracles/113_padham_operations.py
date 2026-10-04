from _rt import *
a = "abc"; bb = a; a = a + "def"
out(a); out(bb); out(b(a == bb)); out(b(bb + "def" == a)); out(b(a != "abcdef"))
out("ab"*3); out(""); out(6); out("Hello, World!?"); out("Hello")
names = ["ann", "", "cy"]
out(0); out("anncy"); out(b(names[1] == ""))
for n in names: out(len(n))
out("a"); out("f"); out("f"); out("bc"); out(b(True)); out(b(True)); out(b(True))
