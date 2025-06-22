import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder

TOKEN = 'типа токен'

# загружаем профессии
def load_professions_from_kdb(kdb_path='professions_db.kdb'): #KDB - ну типа CSV-like формат , мало весит и удобен в редактировании
    professions = []
    try:
        with open(kdb_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or not line.startswith('#PROFESSION|'):
                    continue
                parts = line.split('|')
                if len(parts) < 4:
                    continue
                name = parts[1]
                description = parts[2]
                skills = parts[3].split(',') if parts[3] else []
                professions.append({
                    'name': name,
                    'description': description,
                    'skills': skills
                })
    except FileNotFoundError:
        print(f"Файл {kdb_path} не найден!!!!!!!!!!")
    return professions

professions_db = load_professions_from_kdb()

# подготавливаем данные
tt = []
tl = []
for prof in professions_db:
    skills = prof.get('skills', [])
    examples = [
        f"Мне нравится {', '.join(skills)}",
        f"Я увлекаюсь {', '.join(skills[:2])}",
        f"Интересуюсь {', '.join(skills)}",
        f"Люблю заниматься {', '.join(skills)}",
        f"Мои интересы: {', '.join(skills)}"
    ]
    for ex in examples:
        tt.append(ex.lower())
        tl.append(prof['name'])

vectorizer = TfidfVectorizer(max_features=1000)
X = vectorizer.fit_transform(tt)

le = LabelEncoder()
y = le.fit_transform(tl)

clf = MLPClassifier(hidden_layer_sizes=(128, 64), activation='relu', solver='adam', max_iter=500, random_state=42)
clf.fit(X, y)

def predict_profession(text):
    text_vector = vectorizer.transform([text.lower()])
    pred = clf.predict(text_vector)
    return le.inverse_transform(pred)[0]

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class Form(StatesGroup):
    hobby = State()
    experience = State()
    age = State()
    interests = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Чем любишь заниматься?")

@dp.message(Form.hobby)
async def get_hobby(message: types.Message, state: FSMContext):
    await state.update_data(hobby=message.text.strip())
    await message.answer("Опыт (лет)?")
    await state.set_state(Form.experience)

@dp.message(Form.experience)
async def get_exp(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text.strip())
    await message.answer("Возраст?")
    await state.set_state(Form.age)

@dp.message(Form.age)
async def get_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Ввод только цифрами!")
        return
    await state.update_data(age=int(message.text.strip()))
    await message.answer("Интересы (через запятую)?")
    await state.set_state(Form.interests)

@dp.message(Form.interests)
async def get_interests(message: types.Message, state: FSMContext):
    interests = [i.strip().lower() for i in message.text.split(',')]
    await state.update_data(interests=interests)
    data = await state.get_data()
    await state.clear()

    user_text = f"{data['hobby']} {' '.join(data['interests'])}"

    profession_name = predict_profession(user_text)

    main_prof = None
    for prof in professions_db:
        if prof['name'] == profession_name:
            main_prof = prof
            break

    possible = []
    hobby_lower = data['hobby'].lower()
    interests_lower = [i.lower() for i in data['interests']]
    for prof in professions_db:
        if prof == main_prof:
            continue
        prof_name_lower = prof['name'].lower()
        prof_skills_lower = [s.lower() for s in prof.get('skills', [])]
        if (prof_name_lower in hobby_lower or any(skill in hobby_lower for skill in prof_skills_lower)) or \
           any(interest in prof_skills_lower or interest in prof_name_lower for interest in interests_lower):
            possible.append(prof)
        if len(possible) >= 2:
            break

    if main_prof:
        response = f"*{main_prof['name']}*\n{main_prof['description']}"
        if possible:
            response += "\n\nВозможно, вам также подойдут:\n"
            for p in possible:
                response += f"- {p['name']}\n"
    else:
        response = "Не могу подобрать профессию"

    related = rp(data)
    if related:
        response += "\n\nКосвенно вам могут подойти:\n- " + "\n- ".join(related)

    await message.answer(response, parse_mode='Markdown')

@dp.message()
async def first_step(message: types.Message, state: FSMContext):
    await state.set_state(Form.hobby)
    await get_hobby(message, state)

def rp(user_data):
    hobby = user_data.get('hobby', '').lower()
    interests = user_data.get('interests', [])
    related = []

    if ("физика" in hobby or "физика" in interests) and ("информатика" in hobby or "информатика" in interests):
        related.append("Физик-программист")
        related.append("Специалист по вычислительной физике")
        related.append("Data Scientist в науке")
    if "биология" in hobby or "биология" in interests:
        related.append("Биоинформатик")
    if "роботы" in hobby or "робототехника" in interests:
        related.append("Инженер-робототехник")
    if "медицина" in hobby or "медицина" in interests:
        related.append("Инженер по медицинской физике")
    if "энергетика" in hobby or "энергетика" in interests:
        related.append("Инженер по энергетическим системам")
    if "математика" in hobby or "математика" in interests:
        related.append("Нанотехнолог")
    if "vr" in hobby or "ar" in hobby or "виртуальная реальность" in interests:
        related.append("Разработчик VR/AR")

    return related

if __name__ == "__main__":
    print("Бот запущен")
    asyncio.run(dp.start_polling(bot))
