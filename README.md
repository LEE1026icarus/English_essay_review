# ✍️ Essay Feedback App (Form/Chatbot Integrated)

## 📌 Overview

This Streamlit application provides **integrated essay feedback** in two modes:

* **Form Mode**: Submit a complete essay and receive structured feedback.
* **Chatbot Mode**: Interactively paste paragraphs or sentences and get real-time suggestions.

The app is designed to guide users in writing **balanced opinion essays** with a clear thesis, logical structure, supporting evidence, and proper citations. All interactions and outputs are logged into **Supabase** for tracking.

---

## 🚀 Features

* 🔑 **Login Gate** with shared plaintext password
* 📝 **Form Mode**: One-shot essay feedback (overall comment, strengths, improvements, sentence-level advice, scoring)
* 💬 **Chatbot Mode**: Ongoing interactive feedback with streaming responses
* 📊 **Structured Feedback** aligned with guidelines:

  * Introduction → Thesis statement
  * Body → Topic sentences + supporting evidence
  * Conclusion → Summary & balanced opinion
* 📂 **Supabase Logging**: Saves user ID, essay, feedback, and metadata for later analysis
* 🧭 **Built-in Writing Guide** panel with checklists and citation examples

---

## 🛠️ Tech Stack

* **Frontend**: [Streamlit](https://streamlit.io/)
* **Backend**: [OpenAI GPT models](https://platform.openai.com/docs/)
* **Database**: [Supabase](https://supabase.com/) (logging + user management)
* **Deployment**: Local or cloud hosting

---

## ⚙️ Setup

1. **Clone Repository**

   ```bash
   git clone https://github.com/your-repo/essay-feedback-app.git
   cd essay-feedback-app
   ```

2. **Create Environment & Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set Environment Variables**
   Configure `.env` or `secrets.toml`:

   ```env
   OPENAI_API_KEY=your_openai_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_key   # server-side only
   PLAINTEXT_SHARED_PASSWORD=your_shared_password
   ```

4. **Run App**

   ```bash
   streamlit run app.py
   ```

---

## 📑 Usage

* Open the app in your browser.
* Log in with your **name** and **shared password**.
* Select **Form Mode** or **Chatbot Mode**.
* Input your essay text or sentences.
* Get **structured academic feedback** with improvement suggestions.

---

## 📦 Example Feedback Structure

1. Overall comment (2–3 sentences)
2. Strengths (bullet points)
3. Improvement suggestions (Top 5 with reasoning)
4. Sentence-level edits (original → suggestion → reason)
5. Scores: Structure, Logic, Clarity, Academic Tone, Overall

---

## 🛡️ Notes

* **Do not enter sensitive data** (all inputs are logged).
* Supabase service role key must **only be used on server-side** (never exposed in frontend).
* Citation style: `<Author, Year>` is recommended.

---

## 👨‍💻 Credits

This chatbot was developed by **Sun Hyoung Lee (이순형), Head of Yoonity Lab, Dongguk University**.
