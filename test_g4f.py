import logging
import asyncio
import g4f

class GPTAnswer:
    async def answer(self, text: str, prompt: str, model: str = 'gpt-4', retries: int = 10) -> str | None:
        for i in range(retries):
            try:
                response = await g4f.ChatCompletion.create_async(
                    model=model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text}
                    ],
                )
                if response and "Извините, я не могу" not in response and len(response) > 3:
                    return response
                else:
                    logging.warning(f"GPT response too short or contains refusal: {response}")
            except Exception as e:
                logging.error(f"GPT error (attempt {i+1}/{retries}): {e}")
                await asyncio.sleep(2)
        return None

    async def get_best_answer(self, text: str) -> str | None:
        prompt = """
        """
        return await self.answer(text, prompt)

# Создаем экземпляр класса
gpt = GPTAnswer()

async def main():
    # Используем экземпляр и правильный метод
    answer = await gpt.get_best_answer("Привет!!")
    print(answer)

if __name__ == "__main__":
    # Запускаем асинхронную функцию
    asyncio.run(main())