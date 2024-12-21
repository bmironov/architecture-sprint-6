from locust import HttpUser, between, task

class WebsiteUser(HttpUser):
    wait_time = between(1, 5)
    host = "http://localhost:8080"

    @task
    def index(self):
        self.client.get("/")
