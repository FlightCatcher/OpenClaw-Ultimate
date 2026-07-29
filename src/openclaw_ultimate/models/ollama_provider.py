import ollama


class OllamaProvider:
    def __init__(self, model: str, base_url: str) -> None:
        self.model = model
        self.client = ollama.Client(host=base_url)

    def chat(self, user_message: str, system_prompt: str | None = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        response = self.client.chat(model=self.model, messages=messages)
        return str(response["message"]["content"])
