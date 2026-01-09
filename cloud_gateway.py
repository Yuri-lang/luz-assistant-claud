from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

@app.get('/')
def root():
    return {'message': 'Luz Assistant Cloud', 'status': 'online'}

@app.get('/health')
def health():
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
