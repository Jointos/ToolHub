
import sys

if __name__ == "__main__":
    sili = map(lambda x:list(map(lambda y:y.lower() if y.isupper() else y.upper(),x)),sys.argv[1:])
    def mylambda():
        for item in sili:
            sajt = "".join(item)
            yield sajt
    result = " ".join(mylambda())
    print(result)
