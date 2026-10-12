from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import subprocess

def s2ya(input_text: str) -> str:
    res1 = subprocess.run(
        ["tdmelodic-s2ya"],
        input=input_text,
        text=True,
        capture_output=True,
    )
    return res1.stdout.strip()

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 读取 POST 请求的 Body 长度
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        # 解析请求 JSON
        data = json.loads(post_data)
        texts = data.get("texts", [])
        
        # 拼接文本并调用 s2ya
        combined_input = "\n".join(texts) + "\n"
        output = s2ya(combined_input)
        results = [line.strip() for line in output.split("\n") if line.strip()]
        
        # 返回响应
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = json.dumps({"results": results})
        self.wfile.write(response.encode('utf-8'))

if __name__ == "__main__":
    server_address = ('0.0.0.0', 8000)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print("服务已启动在端口 8000...")
    httpd.serve_forever()