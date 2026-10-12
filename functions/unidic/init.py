import subprocess
import json
from urllib.request import Request, urlopen

def predict_batch(text_list, url="http://localhost:8000"):
    data = json.dumps({"texts": text_list}).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    
    with urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["results"]

def load_t():
    dic_base = subprocess.check_output(["mecab-config", "--dicdir"], text=True).strip()
    dic_path = f"{dic_base}/tdmelodic"
    return dic_path

print("SpeakToYomiAkusento")
print(predict_batch(["私は歌を歌うのが好きです。","なんでこんな目で見てるの"]))

## 加载MeCab
import MeCab
tagger = MeCab.Tagger(f"-d {load_t()}")

#使用MeCab
text = "一昔前は人工知能のプログラミング言語といえばCommon LispやPrologだった。"
output = tagger.parse(text)

print("MeCabDictionaryResult")
print(output.strip())