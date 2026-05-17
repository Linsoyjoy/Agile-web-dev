from app import create_app
from config import DeploymentConfig

app = create_app(DeploymentConfig)
if __name__ == '__main__':
    app.run(debug=True)
