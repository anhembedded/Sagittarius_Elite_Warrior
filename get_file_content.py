import sys
with open(sys.argv[1], 'r') as f:
    print(repr(f.read()))
