import sys

if __name__ == "__main__":
   result = " ".join(map(lambda x:x.upper(),sys.argv[1:]))
   print(result)
