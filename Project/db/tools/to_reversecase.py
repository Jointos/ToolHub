
import sys

if __name__ == "__main__":
   print(list(map(lambda x:list(map(lambda y:y.lower() if y.isupper() else y.upper(),x)),sys.argv[1:])))
