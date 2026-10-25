# Renders docs/demo.gif.  From the repo root:
#   python3 docs/demo/mock_server.py &     # fake virtual hosts on 127.0.0.1/2:18080
#   vhs docs/demo.tape
# Assumes `vheist` is on PATH.  vheist autosaves to its config file, so work on a copy
# of docs/demo/demo.json if you don't want it rewritten.
Output docs/demo.gif
Set Shell "bash"
Set FontSize 14
Set Width 1400
Set Height 760
Set Padding 12
Set TypingSpeed 80ms

Type "vheist --config docs/demo/demo.json" Enter
Sleep 3s
Type "r" Sleep 5s
Tab@300ms 6
Type "admin" Sleep 3s
Tab@300ms 2 Sleep 1s
Down Sleep 1s
Enter Sleep 5s
Escape Sleep 1s
Type "q" Sleep 1s
