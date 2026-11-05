# Retrieval evaluation

Knowledge base: 18 passages · embedding model `intfloat/multilingual-e5-small` · 27 in-scope and 13 out-of-scope questions (`backend/tests/eval_questions.json`).

## Ranking quality (in-scope questions)

| Method | hit@1 | hit@3 | MRR | English hit@3 | Hindi hit@3 |
|---|---|---|---|---|---|
| bm25 | 74% | 96% | 0.85 | 15/16 | 11/11 |
| semantic | 81% | 93% | 0.88 | 14/16 | 11/11 |
| hybrid | 81% | 96% | 0.89 | 15/16 | 11/11 |

Rank of the first relevant passage per question (– = not retrieved by that method):

| Question | BM25 | Semantic | Hybrid | Hybrid top 3 |
|---|---|---|---|---|
| What does Garuda Purana explain about karma? | 1 | 1 | 1 | GPS-05-055, GPS-01-046, GPS-08-101 |
| What does the text describe about the soul? | 1 | 1 | 1 | GPS-01-032, GPS-09-042, GPS-16-005 |
| What is the significance of good deeds? | 1 | 1 | 1 | GPS-14-029, GPS-08-101, GPS-14-048 |
| गरुड़ पुराण में कर्म के बारे में क्या बताया गया है? | 2 | 1 | 2 | GPS-14-029, GPS-09-044, GPS-05-055 |
| गरुड़ पुराण के अनुसार मृत्यु के बाद आत्मा की यात्रा का क्या वर्णन है? | 2 | 2 | 3 | GPS-08-101, GPS-09-042, GPS-01-032 |
| What is the Vaitarani river like? | 1 | 1 | 1 | GPS-02-015, GPS-02-066, GPS-16-005 |
| How can the departed cross the Vaitarani? | 1 | 1 | 1 | GPS-02-066, GPS-02-015, GPS-02-043 |
| Does karma follow a person after death? | 1 | 1 | 1 | GPS-08-101, GPS-05-055, GPS-01-046 |
| How does one attain liberation? | 2 | 1 | 1 | GPS-16-087, GPS-14-077, GPS-16-005 |
| Why should a person give gifts and charity? | 2 | 1 | 1 | GPS-08-110, GPS-08-095, GPS-02-066 |
| What happens to a person at the moment of death? | 1 | 3 | 1 | GPS-01-032, GPS-05-055, GPS-08-095 |
| Who reaches the assembly of the King of Justice? | 1 | 1 | 1 | GPS-14-048, GPS-14-029, GPS-02-043 |
| आत्मा के बारे में क्या कहा गया है? | 1 | 1 | 1 | GPS-09-042, GPS-09-044, GPS-02-066 |
| वैतरणी नदी कैसी है? | 1 | 1 | 1 | GPS-02-066, GPS-02-015, GPS-14-048 |
| मोक्ष कैसे प्राप्त होता है? | 1 | 1 | 1 | GPS-16-087, GPS-16-093, GPS-02-066 |
| दान का क्या महत्व है? | 1 | 1 | 1 | GPS-02-066, GPS-08-110, GPS-05-055 |
| मनुष्य जन्म का क्या महत्व है? | 1 | 1 | 1 | GPS-08-095, GPS-01-046, GPS-16-005 |
| garuda puran mein karma ke baare mein kya kaha hai | 1 | 1 | 1 | GPS-05-055, GPS-08-101, GPS-09-044 |
| What happens after we die? | – | 1 | 2 | GPS-01-046, GPS-08-101, GPS-08-095 |
| Is there life after death? | 3 | 2 | 4 | GPS-16-005, GPS-16-087, GPS-05-055 |
| What is the purpose of human life? | 1 | 1 | 1 | GPS-08-095, GPS-01-046, GPS-14-077 |
| Why do people suffer? | 1 | 4 | 1 | GPS-05-055, GPS-08-095, GPS-16-005 |
| Who is Yama? | 1 | 1 | 1 | GPS-02-082, GPS-01-032, GPS-02-043 |
| What does it say about heaven? | 1 | 7 | 1 | GPS-08-110, GPS-02-066, GPS-09-042 |
| मरने के बाद क्या होता है? | 1 | 1 | 1 | GPS-02-082, GPS-08-101, GPS-08-095 |
| पाप का फल क्या है? | 2 | 1 | 2 | GPS-08-110, GPS-05-055, GPS-08-101 |
| अच्छे कर्म करने से क्या मिलता है? | 1 | 1 | 1 | GPS-14-029, GPS-01-046, GPS-14-077 |

## Relevance gate

Current settings: `STRONG_SEMANTIC_THRESHOLD=0.85`, `SEMANTIC_THRESHOLD=0.8`, `BM25_THRESHOLD=6.0`. A question passes if cosine ≥ strong threshold, or BM25 ≥ its threshold, or cosine ≥ semantic threshold **and** at least one keyword is shared (BM25 > 0).

* Lowest best-cosine among in-scope questions: **0.808**
* Highest best-cosine among out-of-scope questions: **0.828**
* Highest BM25 score among out-of-scope questions: **1.97**
* ⚠️ In-scope and out-of-scope scores overlap — the gate alone cannot separate them; the LLM's `is_answerable` check is the second line of defence.
* Gate decisions correct: **40/40** (round 1: 24/24, round 2: 16/16)

| Round | Type | Question | Best cosine | Best BM25 | Gate | Correct |
|---|---|---|---|---|---|---|
| 1 | in-scope | What does Garuda Purana explain about karma? | 0.832 | 0.79 | pass | ✅ |
| 1 | in-scope | What does the text describe about the soul? | 0.824 | 1.02 | pass | ✅ |
| 1 | in-scope | What is the significance of good deeds? | 0.824 | 3.03 | pass | ✅ |
| 1 | in-scope | गरुड़ पुराण में कर्म के बारे में क्या बताया गया है? | 0.821 | 0.37 | pass | ✅ |
| 1 | in-scope | गरुड़ पुराण के अनुसार मृत्यु के बाद आत्मा की यात्रा का क्या वर्णन है? | 0.830 | 3.83 | pass | ✅ |
| 1 | in-scope | What is the Vaitarani river like? | 0.838 | 4.30 | pass | ✅ |
| 1 | in-scope | How can the departed cross the Vaitarani? | 0.843 | 5.19 | pass | ✅ |
| 1 | in-scope | Does karma follow a person after death? | 0.843 | 2.42 | pass | ✅ |
| 1 | in-scope | How does one attain liberation? | 0.836 | 2.98 | pass | ✅ |
| 1 | in-scope | Why should a person give gifts and charity? | 0.839 | 2.52 | pass | ✅ |
| 1 | in-scope | What happens to a person at the moment of death? | 0.808 | 4.56 | pass | ✅ |
| 1 | in-scope | Who reaches the assembly of the King of Justice? | 0.831 | 6.61 | pass | ✅ |
| 1 | in-scope | आत्मा के बारे में क्या कहा गया है? | 0.832 | 3.83 | pass | ✅ |
| 1 | in-scope | वैतरणी नदी कैसी है? | 0.841 | 6.16 | pass | ✅ |
| 1 | in-scope | मोक्ष कैसे प्राप्त होता है? | 0.822 | 3.39 | pass | ✅ |
| 1 | in-scope | दान का क्या महत्व है? | 0.831 | 2.65 | pass | ✅ |
| 1 | in-scope | मनुष्य जन्म का क्या महत्व है? | 0.871 | 4.29 | pass | ✅ |
| 1 | in-scope | garuda puran mein karma ke baare mein kya kaha hai | 0.841 | 0.79 | pass | ✅ |
| 2 | in-scope | What happens after we die? | 0.814 | 3.01 | pass | ✅ |
| 2 | in-scope | Is there life after death? | 0.809 | 2.17 | pass | ✅ |
| 2 | in-scope | What is the purpose of human life? | 0.844 | 2.67 | pass | ✅ |
| 2 | in-scope | Why do people suffer? | 0.834 | 3.17 | pass | ✅ |
| 2 | in-scope | Who is Yama? | 0.811 | 0.77 | pass | ✅ |
| 2 | in-scope | What does it say about heaven? | 0.814 | 1.91 | pass | ✅ |
| 2 | in-scope | मरने के बाद क्या होता है? | 0.836 | 2.87 | pass | ✅ |
| 2 | in-scope | पाप का फल क्या है? | 0.822 | 3.54 | pass | ✅ |
| 2 | in-scope | अच्छे कर्म करने से क्या मिलता है? | 0.851 | 0.83 | pass | ✅ |
| 1 | out-of-scope | Who won the 2011 Cricket World Cup? | 0.735 | 1.10 | refuse | ✅ |
| 1 | out-of-scope | What does Garuda Purana say about quantum physics? | 0.784 | 0.00 | refuse | ✅ |
| 1 | out-of-scope | How do I bake a chocolate cake? | 0.735 | 0.00 | refuse | ✅ |
| 1 | out-of-scope | What is the best programming language for beginners? | 0.775 | 1.97 | refuse | ✅ |
| 1 | out-of-scope | भारत की राजधानी क्या है? | 0.772 | 0.00 | refuse | ✅ |
| 1 | out-of-scope | आज मौसम कैसा रहेगा? | 0.828 | 0.00 | refuse | ✅ |
| 2 | out-of-scope | What is the capital of France? | 0.742 | 0.00 | refuse | ✅ |
| 2 | out-of-scope | Tell me a joke | 0.790 | 0.00 | refuse | ✅ |
| 2 | out-of-scope | How do I lose weight? | 0.787 | 0.00 | refuse | ✅ |
| 2 | out-of-scope | What does the Bhagavad Gita say about war? | 0.805 | 0.00 | refuse | ✅ |
| 2 | out-of-scope | What is machine learning? | 0.759 | 0.00 | refuse | ✅ |
| 2 | out-of-scope | मुझे एक कहानी सुनाओ | 0.808 | 0.00 | refuse | ✅ |
| 2 | out-of-scope | क्रिकेट का नियम क्या है? | 0.777 | 0.00 | refuse | ✅ |

_Caveat: thresholds are calibrated on this same small question set, so real-world accuracy will be somewhat lower. The LLM is instructed to refuse when passages do not answer the question, as a second safeguard._
