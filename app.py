import dotenv
import project

dotenv.load_dotenv()

app = project.create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)