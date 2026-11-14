from locust import HttpUser, task, LoadTestShape


class InferenceUser(HttpUser):
    @task
    def predict(self):
        self.client.post("/predict", json={"text": "I love this product"})


class StepRamp(LoadTestShape):
    step_users = 1
    step_seconds = 15
    max_users = 20
    last_step = 0

    def tick(self):
        step = int(self.get_run_time() // self.step_seconds) + 1
        if step != self.last_step:
            self.last_step = step
            if self.runner:
                self.runner.stats.reset_all()
        users = step * self.step_users
        if users > self.max_users:
            return None
        return users, 1