import dotenv
import project
import logging

dotenv.load_dotenv()

app = project.create_app()

# Configure logging
logging.basicConfig(filename='/app/logs/karatube.log', level=logging.WARN, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)