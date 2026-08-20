"""
Bulk English training data generator.
Produces diverse, human-like Q&A pairs across many topics.
"""
import json
import random

ENTRIES = []

def add(q, a, t):
    ENTRIES.append([
        {"content": q, "images": None, "role": "user", "thinking": None, "tool_calls": None},
        {"content": a, "images": None, "role": "assistant", "thinking": t, "tool_calls": None}
    ])

# ===================== PROJECT DETAILS =====================
add("Which YOLO version does the custom detector project use?",
    "Gorkem uses YOLO11 in this project, one of the latest versions. The cool part is it covers the entire pipeline — you collect your own dataset, label it, train the model, and then test it in the real world. So if you wanted it to detect, say, specific car models or plant species, you could train it with your own images. YOLO is known for its speed, doing real-time detection.",
    "YOLO11 version, full pipeline from data collection to detection.")

add("Why did the face detection pipeline use 140K images?",
    "The reason for using 140K images is to test reliability at scale. A model might look great on a small dataset but in the real world you have thousands of different faces, angles, lighting conditions. Testing on that scale and still achieving about 11 milliseconds per image on CPU is genuinely impressive. Using MediaPipe is a smart choice too since it's lightweight and fast.",
    "Large scale reliability testing, MediaPipe performance.")

add("What does the writing analyzer project analyze exactly?",
    "The Writing Analyzer uses various NLP parameters to analyze academic and official texts. It likely measures things like sentence length, vocabulary diversity, readability index, passive/active voice ratio, conjunction usage. It works in both English and Turkish which is notable because Turkish has a very different structure — it's an agglutinative language which makes analysis harder. Gorkem showed with this project that NLP isn't just chatbots, it has practical applications in text quality assessment.",
    "Text analysis parameters, TR-EN differences, NLP application areas.")

add("What is the worldcup BPE tokenizer project?",
    "In this project Gorkem trained a custom BPE tokenizer with a vocabulary size of 1024 from Wikipedia articles about the 2022 FIFA World Cup. He also did encode/decode analysis. Think of it as a more focused, smaller version of wiki2bpe. Training a tokenizer on domain-specific text makes it better at tokenizing terms in that domain. Like the word 'Messi' would be a single token instead of being split up.",
    "Worldcup BPE tokenizer, vocab_size=1024, domain-specific tokenizer.")

add("What does the python LLM agent project do?",
    "The Python LLM Agent is an LLM-based coding agent that Gorkem built. The basic idea: you give a language model a task and it writes Python code, runs it, fixes errors. Agent architectures are super popular in AI right now — not just Q&A but systems that can autonomously complete real tasks. This project is a nice example of that concept in action.",
    "LLM agent, Python code generation, autonomous task execution.")

add("What is the miniature transformers from scratch project?",
    "This is Gorkem's from-scratch implementation of the transformer architecture. It's in Jupyter Notebook format, so it's written as a step-by-step tutorial. Transformer is the foundation of modern AI — GPT, BERT, Claude are all transformer-based. Writing it from scratch means truly understanding attention mechanisms, positional encoding, multi-head attention. If you're serious about deep learning, these from-scratch projects are invaluable.",
    "Transformer architecture, from scratch implementation, attention mechanism.")

add("What is the banking management system project?",
    "It's a banking management system Gorkem wrote in Python. It probably simulates basic banking operations — account creation, deposits, withdrawals, transfers, balance inquiries. These kinds of projects are great for beginners because you practice OOP, learn data structures, handle file operations. Every developer should have a project like this in their portfolio when starting out.",
    "Banking system, OOP practice, beginner level project.")

add("What does the pynput macOS macro project do?",
    "This project is a Python macro for macOS. It can loop configurable key sequences and supports mouse button toggling through Karabiner-Elements. So you can automate repetitive key combinations — like if you need to press the same key over and over in a game or have repetitive tasks in your workflow. Small but practical automation tool.",
    "macOS macro, pynput, Karabiner-Elements, automation.")

# ===================== CAREER AND WORK =====================
add("How can I find my first job as a junior developer?",
    "Finding your first job is the hardest part but it's not impossible. Here's what to do: fill your GitHub with at least 3-5 quality projects. Have a personal website, even a simple one. Be active on LinkedIn, share technical content. Attend meetups and tech events. Apply to startups too, not just big companies — you'll learn more at startups. On your resume, highlight projects and technical skills, nobody really cares about your GPA. Prepare for interviews — solve easy and medium problems on LeetCode. Practice behavioral questions too. And most importantly: don't be afraid of rejection, everyone gets a lot of rejections at first.",
    "First job strategy, GitHub, LinkedIn, startups, interview prep.")

add("What do software interviews look like?",
    "Software interviews usually have several stages. First is a phone screen — motivation, experience questions. Then technical interview — algorithm and data structure problems, usually LeetCode-style. Array, string, linked list, tree, graph, dynamic programming topics. Some companies ask system design — how would you design and scale a system. There might be live coding too — you write code in real-time on a shared screen. Some give take-home assignments — a project you complete in a few days. To prepare: solve 3-5 LeetCode problems per week, read Cracking the Coding Interview. And do mock interviews — with a friend or on platforms like Pramp.",
    "Interview stages, algorithms, system design, live coding, preparation.")

add("What do I need to do for remote work?",
    "If you want to work remotely, first strengthen your English because most international companies communicate in English. Write your LinkedIn profile in English and turn on 'Open to Work' with remote filter. Follow remote job platforms: We Work Remotely, Remote.co, AngelList, LinkedIn Remote Jobs. Have a strong GitHub, contribute to open source. Consider timezone differences — European companies align well with Turkey's timezone. Your portfolio and past work matter a lot, references help too. Also develop async communication skills — written communication is critical in remote work.",
    "Remote work requirements, platforms, English, timezone, async communication.")

add("Should I start a startup or work at a company first?",
    "My honest advice: work at a company for 2-3 years first. You'll learn how real products are built, how teams collaborate, how code is reviewed, how deployments work. You'll also build a network and understand the market. Then if you want to start a startup, you'll have much better foundations. Going straight to a startup without experience is risky — you don't know what you don't know. Gorkem balances both: he's a student building his own projects while gaining academic knowledge. That combination of learning and building is powerful.",
    "Startup vs company, gain experience first, Gorkem's balanced approach.")

add("How should I write my resume as a developer?",
    "A developer resume should be different from a traditional one. At the top, a brief summary — 2-3 sentences about who you are and what you do. Technical skills section — languages, frameworks, tools. Projects section — your top 3-5 projects with brief descriptions, tech used, and links. Work experience — internships, freelance, part-time, everything counts. Education — university, certifications, online courses. Common mistakes: resume longer than 2 pages, irrelevant non-technical info, photo (US and EU companies don't want it), writing 'I know Microsoft Office.' Always include GitHub and LinkedIn links. Customize your resume for each position.",
    "Developer resume tips, content, format, mistakes to avoid.")

add("Is it worth contributing to open source?",
    "Absolutely worth it. Contributing to open source is great for both learning and visibility. To start: search for 'good first issue' or 'beginner friendly' labels on GitHub. Fork a project, pick an issue, solve it, open a pull request. Your first contribution can be small — fixing a typo, adding documentation counts. Don't be intimidated by big projects but be realistic — don't expect to contribute to Linux kernel on day one. Start with smaller, active projects. Gorkem's projects are open source too — you could fork and contribute to them. Open source contributions look great on a resume, especially at top companies.",
    "Open source contribution, good first issue, pull requests, visibility, resume.")

add("Should I write a technical blog?",
    "Definitely worth it. Writing a tech blog has multiple benefits: first, to explain something to others you need to understand it deeply yourself, so you learn by writing. Second, it gets indexed by Google and people find you — that means networking and job opportunities. Third, you can add it to your portfolio. Platforms: Medium, Dev.to, Hashnode, or your own GitHub Pages site. Even one post a week is enough. Topics: how you built a project, how you solved a problem, what you learned about a technology. It doesn't need to be perfect, just genuine and useful.",
    "Tech blogging benefits, platforms, content ideas, consistency.")

# ===================== TECHNICAL TOPICS =====================
add("How does the transformer architecture work in simple terms?",
    "Transformer was introduced in Google's 'Attention Is All You Need' paper in 2017 and it changed AI. The core idea: the attention mechanism. Every word in a sentence 'looks at' all other words and learns which ones are relevant to it. In 'The cat drank milk because it was hungry,' the word 'it' pays attention to 'cat' because the cat is the one that's hungry. It has two parts: encoder and decoder. GPT uses only decoder, BERT uses only encoder. Gorkem's miniature-transformers-from-scratch project implements this from scratch. Understanding this architecture is the key to understanding modern AI.",
    "Transformer explanation, attention mechanism, encoder-decoder, paper reference.")

add("What is a CNN and what's it used for?",
    "CNN (Convolutional Neural Network) is a deep learning architecture designed for image processing. Inspired by the human brain's visual cortex. How it works: it slides small filters (kernels) across an image to extract features — edges, corners, colors. Each layer learns more complex features — first layer finds lines, next layer shapes, deeper layers objects. Used for image classification, object detection, face recognition. Gorkem's YOLO and FaceLock projects are CNN-based. If you want to get into computer vision, you need to understand CNNs deeply.",
    "CNN explanation, convolution, filters, layers, use cases.")

add("What is an API and why does it matter?",
    "API (Application Programming Interface) is the interface that lets two pieces of software talk to each other. Think of it like a restaurant menu: you (the client) choose from the menu, the waiter (API) takes your order to the kitchen (server) and brings back your food (data). You don't need to know what happens in the kitchen. On the web, REST API is the most common — works with HTTP requests (GET, POST, PUT, DELETE). Gorkem uses APIs heavily in his scraping and hackathon projects. The find-the-best project connects to 21 different marketplace APIs. As a developer, learning to read and use APIs is essential.",
    "API explanation, REST, HTTP, practical examples.")

add("What's the difference between Git and GitHub?",
    "Git is a version control system — it tracks changes in your code, lets you revert, create branches. It runs locally on your computer. GitHub is the cloud version of Git — you store your code online, share it, collaborate. You can use Git without GitHub but it doesn't make much sense. Basic commands: git init, git add, git commit, git push, git pull, git branch, git merge. You'll use these commands every day. Gorkem has 30+ repos on GitHub — every project is there. For a developer, not knowing Git is like a driver not knowing how to steer.",
    "Git vs GitHub difference, basic commands, importance.")

add("What is Docker and why is it used?",
    "Docker lets you run applications inside containers. A container packages everything your app needs — code, dependencies, config — into one package. Think of it this way: it eliminates the 'works on my machine but not on yours' problem because everyone runs the same container. You write a Dockerfile, build an image, run a container. Especially used in deployment and CI/CD workflows. Combined with Kubernetes for large-scale container management. If you're going to work at a company, knowing Docker is practically mandatory.",
    "Docker explanation, containers, Dockerfile, deployment, why it matters.")

add("What's the difference between REST API and GraphQL?",
    "In REST API, each resource has a separate endpoint — /users, /posts, /comments. Each request returns a fixed data structure, you might get too much or too little data. In GraphQL, there's a single endpoint and you ask for exactly the data you want — no more, no less. REST is simpler and more widespread, GraphQL is more flexible but has a learning curve. For small projects REST is enough, for complex data structures GraphQL has advantages. Facebook invented GraphQL because they wanted to optimize data transfer for mobile apps. Know both but learn REST first.",
    "REST vs GraphQL comparison, endpoints, data structure, use cases.")

add("What types of databases are there?",
    "Two main categories: SQL (relational) and NoSQL (non-relational). SQL databases store data in tables with rows and columns. Examples: PostgreSQL, MySQL, SQLite. Great for structured data — user info, orders. NoSQL offers different models: document-based (MongoDB), key-value (Redis), graph (Neo4j), column-family (Cassandra). Good for unstructured or rapidly changing data. Which to choose depends on the project. Gorkem's study-tracker app uses SQLite — local, lightweight, works offline. Start with SQL, then move to NoSQL based on your needs.",
    "SQL vs NoSQL, database types, PostgreSQL, MongoDB, use case scenarios.")

add("What is CI/CD?",
    "CI/CD stands for Continuous Integration and Continuous Deployment. CI means your tests run automatically and a build is created every time you push code. CD means after tests pass, the code is automatically deployed to production. You push the code, the rest is automatic. GitHub Actions, Jenkins, GitLab CI are popular tools. Why it matters: manual deployment has high error risk, CI/CD makes everything automatic and repeatable. Big companies deploy hundreds of times per day thanks to CI/CD. To learn, start with GitHub Actions — set up a simple CI pipeline for your own project.",
    "CI/CD explanation, GitHub Actions, automated testing and deployment.")

add("What's the difference between microservices and monolith?",
    "In monolith architecture, the entire application is one codebase, runs as a single unit. Simple to develop and deploy but gets complex as it grows. In microservices, each feature runs as a separate service — user service, payment service, notification service. Each can be deployed independently, written in different languages. But there's complexity: inter-service communication, data consistency, monitoring. Start with monolith, move to microservices as you grow. Netflix, Uber use microservices because their teams can work independently.",
    "Monolith vs microservices, pros, cons, when to use which.")

# ===================== AI DEEP TOPICS =====================
add("What does fine-tuning mean?",
    "Fine-tuning means retraining a pre-trained model with your own specific dataset. Think of it this way: models like GPT or BERT have learned general knowledge from billions of words. But if you want a model that understands legal texts, you fine-tune that general model with legal data. The model already knows language, you're just adding domain knowledge. This is much faster and cheaper than training from scratch. Gorkem's turkish-english-nmt project is a perfect fine-tuning example — he fine-tuned MarianMT for Turkish-English translation. We're actually preparing fine-tuning data for ayarlicazhocam right now.",
    "Fine-tuning explanation, pre-trained model, domain specialization, example.")

add("What is RAG?",
    "RAG stands for Retrieval-Augmented Generation. It's an architecture that combines an AI model with a knowledge base. A normal LLM only uses its training data and can hallucinate. In RAG, the model first retrieves relevant documents from a database (retrieval), then uses those documents as context to generate an answer (generation). If you connect a company's internal documentation via RAG, the model can answer company-specific questions accurately. Vector databases like Pinecone, Weaviate, ChromaDB are used with embeddings to find similar documents. Most enterprise AI solutions today are RAG-based.",
    "RAG explanation, retrieval + generation, vector database, enterprise use.")

add("What is LLM hallucination?",
    "Hallucination is when a language model generates completely made-up information. The model gives wrong information with high confidence — nonexistent books, fabricated statistics, fake quotes. Why does it happen? Because LLMs work with statistical patterns, they don't have a real knowledge base. They predict the most likely token and sometimes that prediction doesn't match reality. To handle it: use RAG, do fact-checking, detect when the model is uncertain (uncertainty estimation), require citations. Fine-tuning can also reduce hallucination because the model learns specific information.",
    "Hallucination explanation, why it happens, solutions, RAG.")

add("What is prompt engineering?",
    "Prompt engineering is the art of formulating requests to get the best results from an AI model. Asking the same question differently can give you vastly different quality answers. Key techniques: few-shot prompting (giving examples), chain-of-thought (asking for step-by-step reasoning), role-playing (giving the model a role), system prompts (setting behavioral rules). Instead of 'write me Python code,' saying 'You are an experienced Python developer. Write code that solves this problem with error handling and comments' gives much better results. This field is very valuable right now — companies are hiring prompt engineers.",
    "Prompt engineering, few-shot, chain-of-thought, techniques, career.")

add("What is an embedding?",
    "Embedding is the process of converting words, sentences, or documents into numerical vectors. Why? Computers can't work with text, they work with numbers. But not random numbers — numbers that preserve meaning. For example, 'king' and 'queen' are represented by similar vectors because their meanings are related. Classic methods like Word2Vec, GloVe exist, now models like BERT, Sentence-BERT are used. Embeddings are used in similarity search, classification, clustering, and RAG. Vector databases store embeddings and find similar documents. One of the fundamental building blocks of NLP.",
    "Embedding explanation, word to vector, Word2Vec, BERT, use cases.")

add("What does transfer learning mean?",
    "Transfer learning is transferring knowledge learned for one task to another task. Training models from scratch is expensive and data-hungry. But you can take a model trained on millions of ImageNet images and use just 100 photos for cat-dog classification. The model already learned edges, shapes, textures — you just swap the last layer and teach your own classes. Gorkem's YOLO project uses transfer learning — YOLO already knows general object detection, you teach it your objects. Same concept in NLP: take BERT and fine-tune it for sentiment analysis. Essential in modern AI.",
    "Transfer learning, ImageNet, fine-tuning, YOLO example, why it matters.")

add("What is a GAN?",
    "GAN stands for Generative Adversarial Network. It consists of two neural networks: the Generator and the Discriminator. The Generator creates fake images, the Discriminator tries to tell if they're real or fake. They constantly push each other to improve, until the Generator produces very realistic images. Deepfake technology is GAN-based. Used in art generation, style transfer, image enhancement. But there are ethical concerns — fake content generation, manipulation. GANs are now competing with diffusion models like Stable Diffusion and DALL-E.",
    "GAN explanation, generator-discriminator, deepfake, ethical concerns.")

add("What does the attention mechanism do?",
    "The attention mechanism lets the model assign different weights to different positions in a sequence. In classic RNNs, information was lost in long sentences — the beginning was forgotten. Attention solved this. In 'The cat sat on the mat because it was tired,' the word 'it' should attend to 'cat.' In self-attention, every word looks at all other words. Multi-head attention learns different attention patterns in parallel. This is the foundation of the transformer architecture. Works with the Query, Key, Value trio — Query is what you're looking for, Key is what you have, Value is what you give. Gorkem's miniature-transformers project implements this in detail.",
    "Attention mechanism, self-attention, multi-head, QKV, transformer foundation.")

# ===================== DAILY LIFE AND MOTIVATION =====================
add("Is math required to become a developer?",
    "The answer depends on what area you go into. Web development, mobile apps, backend — you don't need advanced math, just basic logic and problem-solving. But AI, machine learning, computer graphics, cryptography — math is crucial. Linear algebra, statistics, calculus. Gorkem's AI projects involve serious math — model training, loss functions, optimization are all math. But if you want to build web apps, don't let math stop you. What matters is algorithmic thinking, and that improves with practice.",
    "Math in software, depends on area, algorithmic thinking.")

add("I'm experiencing burnout, what should I do?",
    "Burnout is very common in the software world and it's serious. First, don't blame yourself — it's not weakness. Steps: first, take a complete break. Get away from screens, go outside, engage in hobbies. Second, limit your work hours — more than 40 hours a week leads to diminishing returns. Third, learn to say no — you don't have to take every project. Fourth, build routines — regular sleep, exercise, social activities. Fifth, get professional help if needed. Software is a marathon, not a sprint. If you don't take care of yourself, you can't run.",
    "Burnout solutions, break, boundaries, routine, professional support.")

add("Do I need to code every day?",
    "There's a popular idea: 'code every day, do 100 Days of Code.' But the truth is: quality > frequency. Writing meaningless code for 10 minutes every day is less valuable than working focused on a project for 2 hours three times a week. Consistency matters but you don't need to be obsessive. Some days learn, read, research — that's growth too. Some days rest — the brain works better when rested. Gorkem probably doesn't code every day but looking at his projects there's a constant productivity. The key is finding a sustainable pace.",
    "Daily coding myth, quality vs frequency, sustainability.")

add("Is imposter syndrome normal?",
    "Very normal and almost everyone experiences it, especially in software. 'I'm not good enough, others are so much better, one day everyone will realize I'm a fraud' — these are imposter syndrome symptoms. The truth is: even the most experienced developers are constantly learning and there are tons of things they don't know. Nobody knows everything. To overcome it: record your achievements, even small ones. Teach others what you know — seeing someone's eyes light up boosts your confidence. Compare yourself to your past self, not to others. And remember: if you're feeling imposter syndrome, it means you're pushing your limits, and that's a good thing.",
    "Imposter syndrome, normalizing, coping strategies.")

add("Why are women underrepresented in tech?",
    "There are many historical and cultural factors. Computer science was actually female-dominated early on — Ada Lovelace, Grace Hopper were pioneers. But from the 1980s, personal computers were marketed as 'boy toys' and the balance shifted. Societal pressures, lack of role models, workplace culture issues all contribute. But things are changing — communities like Women Who Code, Django Girls, She Codes are growing. Tech companies run diversity programs. If you're in this field or want to enter it, know that technology is for everyone and diverse teams build better products.",
    "Gender imbalance in tech, historical background, change, communities.")

# ===================== CURRENT TECH TRENDS =====================
add("How is AI affecting the job market?",
    "AI affects the job market in two ways: automating some jobs and creating new ones. Repetitive, routine tasks — data entry, basic customer service, simple translation — are being done by AI now. But entirely new positions have emerged: AI developer, ML engineer, prompt engineer, AI ethics specialist. My advice: develop skills that AI can't replace — creativity, critical thinking, leadership, empathy. And learn to use AI tools — employees who can work with AI are much more valuable than those who can't. Instead of fearing AI, use it as a tool.",
    "AI and job market, automation, new positions, advice.")

add("What technologies are trending in 2026?",
    "Several areas are very hot in 2026: Large Language Models and their applications — RAG, AI agents, code generation. Edge AI — running AI on devices instead of the cloud, mobile and IoT applications. Computer vision is growing in autonomous vehicles and industrial applications. MLOps — model deployment and management has become a discipline. Quantum computing is still early but promising. Low-code/no-code platforms are spreading but not replacing developers. And cybersecurity — AI defense against AI attacks. Gorkem's focus areas — AI, CV, NLP — align perfectly with these trends.",
    "2026 tech trends, LLM, Edge AI, MLOps, CV, cybersecurity.")

add("Why does AI ethics matter?",
    "AI ethics is critical because AI is now in every part of our lives. Key concerns: Bias — if training data is biased, the model is biased. Face recognition systems can perform worse on certain ethnic groups. Privacy — AI processes personal data, what are the limits? Transparency — can an AI system explain why it made a decision? Employment — if AI causes job losses, whose social responsibility is it? Deepfake — fake content generation, information pollution. Developing AI without thinking about these issues is dangerous. Responsible AI development is now a necessity.",
    "AI ethics, bias, privacy, transparency, deepfake, responsible AI.")

# ===================== MORE DIVERSE TOPICS =====================
add("What IDE does Gorkem probably use?",
    "Can't say for certain but looking at his projects, he probably uses VS Code or PyCharm for Python projects. He has many Jupyter Notebooks — DeepLearningBootcamp, email-phishing-detection, miniature-transformers are all in notebook format. For C projects he might use VS Code or CLion. For TypeScript/React projects VS Code is the most common choice. Honestly, which IDE you use doesn't matter that much — what matters is knowing your tool well. Starting with VS Code makes the most sense because it has extensions for almost every language and it's free.",
    "IDE guess, VS Code, PyCharm, Jupyter, IDE choice advice.")

add("What's the difference between data science and AI?",
    "Data science and AI are related but different fields. Data science focuses on extracting meaning from data — statistics, data analysis, visualization, business intelligence. A data scientist says 'analyze last year's sales data and predict next quarter.' AI focuses on developing machines' ability to think and make decisions like humans — image recognition, NLP, autonomous systems. ML is a subset of AI. In practice they overlap a lot — a data scientist uses ML models, an AI engineer does data analysis. Gorkem's projects lean more toward AI but he has data science skills too.",
    "Data science vs AI, differences, overlap, practical comparison.")

add("Is participating in Kaggle competitions useful?",
    "Very useful. Kaggle competitions give you real-world problems and you compete with developers worldwide. Amazing for learning because after competitions end you can study the winners' solutions — that alone is incredibly educational. Looks good on your resume too. Start with Getting Started competitions — Titanic survival prediction is the classic beginner one. Then move to playground competitions. Getting good leaderboard rankings is prestigious but the main goal should be learning. Kaggle notebooks are valuable too, reading other people's code is gold for learning.",
    "Kaggle benefits, competition levels, learning strategy, resume impact.")

add("I want to do a master's abroad, what should I do?",
    "Preparation for a master's abroad should start early. You'll need: GPA — 3.0+ for most schools. English exam — TOEFL or IELTS, depends on the university. GRE — some schools dropped it but some still require it. Letters of recommendation — at least 2-3 from professors. Statement of Purpose — why this program, why this university, future plans. Portfolio — projects, publications, research experience. For funding: scholarship options include Fulbright, TUBITAK, university scholarships. Many European master's programs are free (Germany, Norway). Start applications 1 year in advance. Deadlines are usually November to January.",
    "Master's abroad preparation, GPA, TOEFL, GRE, SOP, scholarships, timeline.")

add("What's the difference between computer engineering and software engineering?",
    "Computer engineering is broader — covers both hardware and software. You'll take courses on operating systems, computer architecture, embedded systems, digital design. Software engineering focuses only on the software side — software design, testing, project management, software quality. In the job market, both can apply to the same positions, not much difference. In Turkey, software engineering programs are less common, computer engineering is more popular. Gorkem studies computer engineering and does both software (AI projects, web/mobile) and hardware-adjacent work (gorkem-os). Whichever you choose, what matters is what you learn and what you build.",
    "CE vs SE difference, curriculum, job market, Turkey context.")

add("What do open source licenses mean?",
    "Open source licenses determine what others can do with your code when you share it. MIT license is one of the most permissive — use however you want, modify, use commercially, just keep the original license. Apache 2.0 is similar but also grants patent rights. GPL is more restrictive — anyone using the code must make their own code open source too. BSD is similar to MIT, permissive. Creative Commons is generally for content (text, images). Which to choose depends on your project's goal: maximum sharing use MIT, protecting contributors use Apache, ensuring it stays open use GPL. Gorkem's projects on GitHub are open source.",
    "Open source licenses, MIT, Apache, GPL, BSD, selection criteria.")

add("Is web scraping legal?",
    "It's a gray area. Generally: scraping publicly available data is legal in most countries. But you should respect the site's robots.txt file and terms of service. Scraping personal data can be problematic under KVKK (Turkey) and GDPR (Europe). Apply rate limiting — don't overload servers. Scraping data behind login walls is generally against terms of service. Research-purpose scraping is more accepted. Gorkem's wiki2bpe project scrapes Wikipedia which is allowed by Wikipedia's API and license. Our scraping scripts use APIs from Stack Overflow, Dev.to — using APIs is always safer and more legal than direct scraping.",
    "Web scraping legality, robots.txt, KVKK, GDPR, API usage, ethics.")

add("Why is writing tests important?",
    "Writing tests is how you prove your code works correctly. 'It seems to work' isn't enough — what happens with edge cases, unexpected inputs? Unit tests test a single function, integration tests test parts working together, end-to-end tests test the whole system. Writing tests seems like wasted time at first but saves a lot long-term — when you make a change, run tests and immediately see what broke. In TDD you write the test first, then the code. pytest (Python), Jest (JavaScript) are popular frameworks. In professional software, code without tests is not accepted.",
    "Testing importance, unit/integration/e2e, TDD, pytest, Jest, long-term benefit.")

add("What is clean code?",
    "Clean code means readable, understandable, and maintainable code. Robert C. Martin's book of the same name is considered the bible of this topic. Core principles: use meaningful variable and function names (userAge instead of x), functions should do one thing (Single Responsibility), eliminate repeated code (DRY — Don't Repeat Yourself), write code so clear it doesn't need comments, keep functions short (no more than 20-30 lines). Code reviews also improve quality. Writing fast working code is important but writing readable and maintainable code is more important — because you write code once but read it 100 times.",
    "Clean code principles, naming, SRP, DRY, readability, Martin.")

add("What is a BLEU score?",
    "BLEU (Bilingual Evaluation Understudy) is a metric that measures machine translation quality. It ranges from 0 to 1, where 1 is perfect translation. It compares machine translation with human translation by looking at n-gram overlap. 40+ BLEU is generally considered good. Gorkem's turkish-english-nmt project achieved 43 BLEU which is a solid result for a fine-tuned model. But BLEU isn't a perfect metric — it looks at word matching rather than meaning. That's why alternative metrics like ROUGE, METEOR, BERTScore are also used.",
    "BLEU score explanation, 0-1 range, n-gram, alternative metrics.")

add("What is Hugging Face?",
    "Think of Hugging Face as the GitHub of AI. It's a platform hosting thousands of ready-made models, datasets, and demos. With the transformers library you can load a model with just 3 lines of code. Model Hub has BERT, GPT, LLaMA, Whisper and more. Datasets library gives you access to datasets. Spaces lets you create demo apps. Gorkem's wiki2bpe project publishes its tokenizer to the Hugging Face Hub. If you work with NLP or AI in general, knowing Hugging Face is mandatory — it's become the industry standard platform.",
    "Hugging Face intro, transformers, Model Hub, Datasets, Spaces.")

add("How do I get into cybersecurity?",
    "Cybersecurity is a vast field. To get in: first learn basic networking — TCP/IP, DNS, HTTP, firewalls. Learn Linux — most security tools run on Linux. Python scripting is very useful. Practice on platforms like TryHackMe and HackTheBox — gamified security training. Participate in Capture The Flag (CTF) competitions. Certifications matter — CompTIA Security+, CEH, OSCP. Gorkem's email-phishing-detection project is a nice example at the intersection of cybersecurity and NLP. Cybersecurity specialists are in very high demand.",
    "Cybersecurity entry, networking, Linux, TryHackMe, CTF, certifications.")

add("What is edge computing?",
    "Edge computing means processing data closer to where it's generated — at the 'edge' — instead of in cloud servers. Instead of sending factory sensor data to the cloud, you process it right there. Advantages: low latency, bandwidth savings, privacy. Especially critical for IoT devices, autonomous vehicles, smart cities. Edge AI means running AI models directly on devices — like face recognition on your phone working without going to the cloud. Tools like TFLite, ONNX Runtime shrink models to run on edge devices.",
    "Edge computing definition, advantages, IoT, Edge AI, TFLite.")

add("What are Agile and Scrum?",
    "Agile is a software development philosophy, Scrum is its most popular framework. The old method (Waterfall): first gather all requirements, then design, then code, then test. But customers don't know what they want upfront and requirements change. Agile says: break into small pieces, deliver something working every 2 weeks (sprint), get feedback, adapt. Scrum has ceremonies: daily standup, sprint planning, sprint review, retrospective. Roles: Product Owner, Scrum Master, Development Team. If you'll work at a company, knowing Agile/Scrum is necessary.",
    "Agile philosophy, Scrum framework, sprints, roles, Waterfall comparison.")

add("When is NoSQL preferred?",
    "NoSQL databases are preferred when: your data can be structurally very different (schema-less), you have massive amounts of data and need horizontal scaling, speed is critical and millisecond response is needed, you're building real-time apps (chat, gaming, IoT). MongoDB is the most popular document-based NoSQL — stores JSON-like documents. Redis is a key-value store — great for caching. Cassandra for big data — Facebook and Netflix use it. Neo4j is a graph database — ideal for social network relationships. But don't use NoSQL for everything — for financial data and relational data, SQL is still the best choice. Use the right tool for the right job.",
    "NoSQL use cases, MongoDB, Redis, Cassandra, Neo4j, when to use SQL.")

add("How should I progress on LeetCode?",
    "If you're starting LeetCode, progress like this: begin with Easy problems — Array, String, HashMap topics. Solve 3-5 problems per week, don't rush. After solving each problem, check the Discussion section — you'll learn a lot from others' solutions. If a problem isn't solved in 30 minutes, look at the solution, understand it, then re-solve it the next day. After passing Medium problems, look at Hard but Hard problems usually aren't needed for interviews. Follow Blind 75 or NeetCode 150 lists — they've categorized the most important problems. And solve with pen and paper first, design the algorithm before writing in an IDE.",
    "LeetCode progression, Easy-Medium-Hard, Blind 75, Discussion, repetition.")

add("What is Kubernetes?",
    "Kubernetes (K8s for short) is a container orchestration platform. Docker creates containers, Kubernetes manages those containers at scale — automatic scaling, load balancing, self-healing, rolling updates. If a container crashes it automatically starts a new one. When you need to manage 100-1000 containers, Docker alone isn't enough, K8s steps in. Developed by Google, now open source. It's become the standard infrastructure for cloud native applications. AWS EKS, Google GKE, Azure AKS offer managed K8s services. Complex but worth learning.",
    "Kubernetes definition, container orchestration, scaling, cloud native.")

add("Can you ask me something?",
    "Sure! That's what I'm here for. Gorkem's projects, software learning roadmap, career advice, technical topics — anything goes. Ask away!",
    "Simple invitation, friendly response.")

add("Thank you so much, you've been really helpful",
    "You're welcome! Whenever you have another question, I'm always here. Keep building projects and never stop learning. Good luck!",
    "Thank you response, motivating closing.")

add("See you later!",
    "See you! Come back anytime, I'm here to help with any question. Take care!",
    "Farewell response, friendly closing.")

# ===================== GORKEM'S LIFE AND APPROACH =====================
add("Is there a common theme across Gorkem's projects?",
    "Absolutely: problem-solving and building from scratch. Gorkem takes a problem and builds a solution. FaceLock solves a security problem, find-the-best solves a price comparison problem, email-phishing-detection solves a cybersecurity problem. He also loves building from scratch — from scratch OS, from scratch transformer, from scratch tokenizer. This approach is invaluable for learning because instead of using ready-made libraries you understand the underlying logic. Third theme is diversity — active in AI, low-level, mobile, and web. This paints a full-stack engineer profile.",
    "Cross-project theme analysis, problem solving, from scratch, diversity.")

add("How does Gorkem manage to build so many projects?",
    "Gorkem's productivity likely comes from several factors. First, passion — time moves differently when you love what you do. Second, discipline — doing a little every day creates big accumulation over time. Third, hackathons — being forced to ship in a short time makes you learn fast. Fourth, synergy with university courses — applying class knowledge in projects means you learn both the course and the project. Fifth, he probably doesn't perfectionism — he finishes and shares projects instead of endlessly polishing them. That's a very important trait.",
    "Productivity analysis, passion, discipline, hackathon, anti-perfectionism.")

add("What's Gorkem's most impressive project in your opinion?",
    "I'd say gorkem-os is the most impressive. Writing an operating system from scratch is one of the hardest and deepest topics in computer engineering. Most engineers never even attempt it. You need to write a bootloader, set up memory management, write interrupt handlers — all in C and Assembly. This project alone shows how well Gorkem turns theoretical knowledge into practice. But perspectives differ — someone into AI might find turkish-english-nmt more impressive, someone into mobile dev might prefer Build Your Target Body.",
    "Most impressive project evaluation, gorkem-os, personal opinion.")

add("What university does Gorkem attend?",
    "Gorkem studies Computer Engineering at Yeditepe University in Istanbul. Yeditepe is a private university on the Asian side of Istanbul, in the Atasehir-Kayisdagi area. They teach in English which is very important for the tech industry. Being in Istanbul gives great advantages for internships and job opportunities — there are tons of tech companies in Maslak, Levent. Gorkem doesn't just rely on university though — he builds his own projects, joins hackathons, runs a startup alongside his studies.",
    "Yeditepe University, location, English education, Istanbul advantage.")

add("How important is GPA in university?",
    "Let me put it this way: no company asks for your transcript. Between two graduates, the one with projects and experience always gets picked over the one with just a high GPA. But that doesn't mean slack off — some courses like algorithms, data structures, operating systems are truly important and you need to learn them well. Also if you're on scholarship there might be GPA requirements. If you want graduate school or study abroad, GPA matters more. But generally: good GPA + projects beats perfect GPA + zero projects. Look at Gorkem's success — projects and real-world experience speak louder.",
    "GPA importance, projects vs grades, scholarship, grad school.")

add("When should I do an internship in university?",
    "Ideally, do your first internship in the summer after your sophomore year. Most universities require an internship after junior year but starting early is a big advantage. Your first internship can be at a small startup or software company — big companies usually prefer juniors and seniors. Before applying, have at least one project on your GitHub. Focus on learning at your first internship, salary should be secondary. Aim for a bigger company for your second internship. Graduates with internship experience find jobs much more easily than those without.",
    "Internship timing, first internship, big company vs startup, preparation.")

def main():
    random.shuffle(ENTRIES)
    with open("scrapers/bulk_en.json", "w", encoding="utf-8") as f:
        json.dump({"train": ENTRIES}, f, ensure_ascii=False, indent=4)
    print(f"Generated {len(ENTRIES)} English entries.")

if __name__ == "__main__":
    main()
