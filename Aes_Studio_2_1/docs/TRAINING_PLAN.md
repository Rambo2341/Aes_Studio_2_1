# خطة تدريب Aes — Aes Training Plan

Aes يتعلم بطريقتين مختلفتين، ولازم تفرّق بينهم:

| الطريقة | وش تسوي | متى تتغير |
|---|---|---|
| **المعرفة والذاكرة** (Knowledge / Memory) | يقرأ صفحات ومجلات وكتب ومقاطع، ويحفظ ملاحظات مع مصادرها ويرجع لها بـ `recall` | فوراً، كل ليلة |
| **تدريب العقل** (LoRA fine-tuning) | يغيّر طريقة تفكير الموديل نفسه: أسلوبه، وكوده، واستخدامه للأدوات | كل ما يتجمع عندك بيانات كافية (أسابيع) |

ابدأ بالأولى على طول. الثانية تجي بعدين.

---

## المرحلة 0: التجهيز (يوم واحد)

1. `run_windows.bat`، وبعدين من **Models** اختر العقل واضغط **Test model** ثم **Set default**.
   - عشان يشوف الشاشة لازم عقل يدعم الصور (vision): Claude، أو Ollama مع موديل vision مثل `qwen2.5vl`.
2. أدوات التعلم الإضافية:
   ```
   pip install -r requirements-learning.txt
   python -m playwright install chromium
   ```
3. هارد خاص للذاكرة: غيّر اسم `aes_data_location.example.txt` إلى `aes_data_location.txt` واكتب فيه مثلاً `D:\AesBrain`.
4. من الشات اختر وضع الثقة **Auto** (يمشي حسب سياسة كل أداة) أو **Full access** (بدون أي سؤال).

## المرحلة 1: المدرسة (كل ليلة)

المنهج موجود في `curriculum/aes_curriculum.json`، وفيه 41 وحدة بالترتيب: **ابتدائي ← متوسط ← ثانوي ← جامعة ← تخصص**. المسارات:

`computer` استخدام الجهاز وكروم · `programming` (JS/TS، Lua/Luau، C#، C++، Git، خوارزميات) · `roblox` · `3d` (Blender) · `unity` · `math` · `physics` · `chemistry` · `ai`

كل وحدة تتحول إلى هدفين:
1. **Study:** يبحث في النت، ويقرأ المصادر الرسمية، ويكتب ملاحظات مع ذكر المصادر.
2. **Practice:** تمرين حقيقي له "تعريف إنجاز" (Definition of Done). يكتب الكود ويشغّله، أو يتحكم بالشاشة ويتأكد، أو يتحقق من الرياضيات بـ Python.

تشغيله:
- **من الواجهة:** صفحة **Autopilot**، ثم **Load training plan**، ثم **Run Autopilot now**.
- **من الطرفية:**
  ```
  python main.py --curriculum computer,programming --max-level middle
  run_autopilot.bat
  ```
  الأفضل تبدأ بـ `computer` عشان يتعلم يستخدم جهازك قبل أي شي ثاني. بعدها زِد المستوى شوي شوي.

التقرير يطلع الصبح في `<data>\reports\autopilot_*.md`.

## المرحلة 2: المكتبة والمجلات والمقاطع

| المصدر | كيف |
|---|---|
| مجلد كتب ومجلات (PDF/DOCX/TXT) | `python main.py --library "D:\Books"` أو قول له بالشات: "استورد مجلد D:\Books" |
| مجلة أو كتاب واحد | بالشات: "اقرأ D:\Books\mag.pdf واحفظه" (أداة `read_document`) |
| صفحة ويب | `fetch_url`، والمواقع اللي تعتمد على JavaScript تنقرأ بـ `render=true` |
| مقطع يوتيوب | `python main.py --video "https://youtu.be/..." --detail "Recursion"` أو بالشات: "تعلم من هالمقطع ..." |
| مقطع على جهازك | نفس الشي بمسار الملف، ويحوّل الصوت لنص بـ faster-whisper |
| موضوع كامل | `python main.py --learn "Linear algebra"` |

المقاطع يقرأها من الترجمة أو من الصوت المحوّل لنص. ما يفهم الصورة داخل المقطع إطار بإطار.

## المرحلة 3: جمع بيانات تدريب العقل (2 إلى 6 أسابيع)

كل ما يسوي Aes شغل ممتاز، اضغط 👍 عليه في الشات. هذي الردود هي اللي بيتعلم منها العقل.

1. **Training Lab**، ثم **Collect**، ثم **Export JSONL**.
2. الهدف: **500 مثال ممتاز على الأقل**، و2000 أو أكثر أفضل. الجودة أهم من العدد.
3. نوّع الأمثلة: Luau، C#، C++، JS، Blender، تحكم بالجهاز، عربي وإنجليزي.

## المرحلة 4: تدريب Aes 3.0 (LoRA)

اختر الموديل الأساسي حسب ذاكرة كرت الشاشة عندك (VRAM). السكربت الحالي يدرّب بدقة كاملة، فهذي الأرقام تقريبية:

| VRAM | موديل أساسي مقترح |
|---|---|
| 8 GB | `Qwen/Qwen2.5-Coder-1.5B-Instruct` |
| 12–16 GB | `Qwen/Qwen2.5-Coder-3B-Instruct` |
| 24 GB أو أكثر | `Qwen/Qwen2.5-Coder-7B-Instruct` |
| أقل من كذا | استأجر GPU سحابي لساعات قليلة (A100/H100) |

```
pip install -r trainer/requirements-training.txt
python trainer/train_lora.py --base Qwen/Qwen2.5-Coder-3B-Instruct --dataset exports\aes_training_XXXX.jsonl --output models\aes3-lora --epochs 2
python trainer/merge_lora.py --base Qwen/Qwen2.5-Coder-3B-Instruct --adapter models\aes3-lora --output models\aes3-merged
```

بعدها حوّله إلى GGUF بأدوات llama.cpp (`convert_hf_to_gguf.py` ثم `llama-quantize` بصيغة Q4_K_M). بعدها في **Models** سوّ بروفايل `Aes 3.0` من نوع `llama_cpp` واختر ملف الـ GGUF.

## المرحلة 5: الاختبار قبل الاعتماد

1. صفحة **Evals**: شغّل الاختبارات على العقل القديم وعلى Aes 3.0.
2. اعتمد Aes 3.0 بس إذا نتيجته **أعلى أو تساوي** القديم.
3. خلّ النسخة القديمة موجودة عشان ترجع لها إذا احتجت.

## الدورة المستمرة

```
كل ليلة:     Autopilot → يدرس ويتمرن → تقرير الصبح
كل يوم:      تستخدمه وتقيّم الردود 👍 / 👎
كل شهر:      Export → LoRA → Evals → اعتماد Aes 3.x
```

## حدود لازم تعرفها
- اللي يقرأه Aes يروح للمعرفة والذاكرة، مو لعقل الموديل. العقل يتغير بس بالمرحلة 4.
- التعلم من المقاطع يعتمد على الترجمة والكلام المنطوق.
- القراءة والتحكم بالجهاز كلها تمشي حسب الصلاحيات اللي تختارها أنت، وكل حركة تنسجل في السجل.
- احترم حقوق النشر: استخدم كتب ومجلات تملكها أو مصادر مجانية ومفتوحة.
