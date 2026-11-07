"""只供本机手动验收：模拟 Chat Completions 服务，不连接外网。"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/v1/chat/completions':
            self.send_error(404)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            request = json.loads(self.rfile.read(size))
            assert request['messages'][-1]['role'] == 'user'
            assert request['messages'][1]['content'].startswith('Current visible Balatro state')
        except (ValueError, KeyError, AssertionError):
            self.send_error(400)
            return
        answer = '本地测试成功：牌灵已收到当前局面和你的问题。这是测试回复，不是真实策略建议。'
        data = json.dumps({'choices': [{'message': {'content': answer}}]}, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    print('牌灵本地测试服务：http://127.0.0.1:8765/v1/chat/completions', flush=True)
    HTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
