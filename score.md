Rubric ระดับคุณภาพสำหรับประเมิน Final Project
การประเมิน Final Project ใช้ระดับคุณภาพ 5 ระดับ เพื่อวัดความสามารถของโครงการตั้งแต่การพัฒนาระบบพื้นฐาน ไปจนถึงการออกแบบระบบ RAG ที่มีการบูรณาการ Dense Retrieval, Graph RAG, Hybrid RAG, Local LLM และ API LLM อย่างเป็นระบบ
การพิจารณาคะแนนไม่ได้พิจารณาเพียงว่า “มี Technology หรือไม่” แต่พิจารณาถึง คุณภาพของการนำไปใช้จริง ความถูกต้องของการออกแบบ การบูรณาการ ประสิทธิภาพ และความสามารถในการวิเคราะห์ผลการทดลอง

ระดับคุณภาพโดยรวม
ระดับ
ระดับคุณภาพ
ลักษณะของ Project
Level 5
Excellent / Advanced
ระบบสมบูรณ์ มีการบูรณาการเทคโนโลยีอย่างเหมาะสม มีการทดลองและวิเคราะห์เชิงลึก
Level 4
Very Good
ระบบครบตามข้อกำหนด ทำงานได้ดี และมีการปรับปรุงหรือประเมินผลอย่างชัดเจน
Level 3
Good / Satisfactory
ระบบทำงานได้ตามข้อกำหนดหลัก แต่การบูรณาการและการวิเคราะห์ยังมีข้อจำกัด
Level 2
Basic / Developing
มีการพัฒนาองค์ประกอบบางส่วน แต่ระบบยังไม่สมบูรณ์หรือทำงานร่วมกันได้จำกัด
Level 1
Limited / Beginning
มี Prototype หรือการสาธิตบางส่วน แต่ไม่สามารถแสดงระบบ RAG ตามข้อกำหนดได้ครบถ้วน


1. Data & Knowledge Base พีท
คำถาม: 

เก็บเป็น JSON MOCK ไว้ 
 
หนังสือ เอกสารในการแนะนำบุคลิกภาพ คลังในการช่วจับคู่มาทำRAG


Level 5
มีการออกแบบ Dataset และ Knowledge Base อย่างเป็นระบบ มี Data Cleaning, Chunking, Metadata และการเตรียมข้อมูลสำหรับทั้ง Vector และ Graph อย่างเหมาะสม สามารถอธิบายเหตุผลของการออกแบบได้ และข้อมูลมีคุณภาพเพียงพอสำหรับการทดลอง
Level 4
เตรียมข้อมูลสำหรับ Vector และ Graph ได้ครบ มีการจัดโครงสร้างและทำความสะอาดข้อมูลเหมาะสม แต่ยังขาดการปรับปรุงหรือวิเคราะห์ข้อมูลในบางส่วน
Level 3
มี Dataset และสามารถนำไปสร้าง Vector และ Graph ได้ แต่การเตรียมข้อมูลยังเป็นพื้นฐาน
Level 2
มี Dataset แต่การเตรียมข้อมูลยังไม่สมบูรณ์ หรือมีปัญหาเรื่อง Chunking / Metadata / Graph Structure
Level 1
มีข้อมูลสำหรับทดลองเพียงเล็กน้อย หรือไม่สามารถอธิบายกระบวนการเตรียมข้อมูลได้

2. Dense RAG ฟาริก
Level 5
Dense RAG ทำงานครบตั้งแต่ Embedding → Vector Retrieval → Context Selection → LLM และมีการปรับ Retrieval เช่น Top-K, similarity threshold, reranking หรือวิธีอื่น พร้อมมีผลการทดลองยืนยันคุณภาพ
Level 4
Dense RAG ทำงานครบและให้ผลลัพธ์ที่เหมาะสม มีการกำหนด Retrieval Strategy อย่างชัดเจน
Level 3
Dense RAG ทำงานได้จริงตั้งแต่ Vector Search ถึง LLM แต่ใช้ Configuration พื้นฐานและยังไม่มีการปรับปรุงมากนัก
Level 2
สามารถสร้าง Vector Search ได้ แต่การนำ Retrieval มาใช้กับ LLM ยังไม่สมบูรณ์
Level 1
มีเพียง Embedding / Vector Database หรือ Prototype แต่ไม่สามารถแสดง Dense RAG ที่ทำงานครบกระบวนการได้

3. Graph RAG บังเมษ
Level 5
มีการออกแบบ Knowledge Graph ที่เหมาะสม มี Node และ Relationship ที่มีความหมาย ใช้ Graph Retrieval เพื่อสนับสนุนการตอบคำถามจริง และสามารถอธิบายได้ว่า Graph ช่วยแก้ข้อจำกัดของ Dense Retrieval อย่างไร
Level 4
Graph RAG ทำงานได้จริง มี Graph Query / Retrieval และนำข้อมูลเข้าสู่ LLM ได้อย่างถูกต้อง
Level 3
มี Graph Database และสามารถใช้ Graph Retrieval ร่วมกับ LLM ได้ แต่การออกแบบ Graph หรือการใช้ประโยชน์จาก Relationship ยังอยู่ในระดับพื้นฐาน
Level 2
สร้าง Graph ได้ แต่การนำ Graph มาใช้ใน Retrieval หรือการสร้างคำตอบยังจำกัด
Level 1
มีเพียง Graph Database หรือสร้าง Node/Relationship ตัวอย่าง แต่ยังไม่สามารถแสดง Graph RAG ได้จริง

4. Hybrid RAG
หัวข้อนี้ควรเป็นหัวใจสำคัญของการประเมิน
Level 5
สามารถบูรณาการ Dense Retrieval และ Graph Retrieval ได้อย่างเป็นระบบ มี Fusion / Ranking / Routing / Context Aggregation ที่เหมาะสม และมีผลการทดลองแสดงให้เห็นถึงประโยชน์ของ Hybrid RAG อย่างชัดเจน
Level 4
สามารถใช้ Dense และ Graph Retrieval ร่วมกันได้จริง มีการออกแบบกระบวนการรวมผลลัพธ์อย่างชัดเจน และระบบทำงานได้ดี
Level 3
สามารถรวม Dense และ Graph Retrieval ในระบบเดียวกันได้ แต่การ Fusion หรือการเลือก Context ยังเป็นวิธีพื้นฐาน
Level 2
มีทั้ง Dense และ Graph แต่ส่วนใหญ่ทำงานแยกกัน หรือการเชื่อมต่อระหว่างสอง Retrieval ยังไม่ชัดเจน
Level 1
มี Dense และ Graph อยู่ใน Project แต่ไม่ได้ใช้ร่วมกันในการสร้างคำตอบ

5. Local LLM 
Level 5
เลือก Local LLM ได้เหมาะสมกับ Hardware และงาน มีการปรับ Configuration / Prompt / Context และมีการวัด Resource Usage, Response Time หรือข้อจำกัดอย่างเป็นระบบ
Level 4
Local LLM ทำงานร่วมกับ RAG ได้ดี และมีการวิเคราะห์ Model หรือ Resource อย่างเหมาะสม
Level 3
Local LLM ทำงานร่วมกับ RAG ได้จริง แต่ใช้ Configuration พื้นฐาน
Level 2
สามารถเรียก Local LLM ได้ แต่การเชื่อมต่อกับ RAG ยังไม่สมบูรณ์
Level 1
มีการติดตั้งหรือทดลอง Model แต่ไม่สามารถใช้งานในระบบจริงได้

6. API LLM
Level 5
API LLM ถูกนำมาใช้จริง มีการจัดการ Prompt, Context, Token และ Error อย่างเหมาะสม พร้อมวิเคราะห์ Response Time และ Cost หรือ Resource Usage
Level 4
API LLM ทำงานร่วมกับ RAG ได้ดี และมีการวิเคราะห์ผลลัพธ์
Level 3
API LLM ทำงานร่วมกับ RAG ได้จริงในระดับพื้นฐาน
Level 2
สามารถเรียก API ได้ แต่ยังไม่สามารถบูรณาการกับระบบ RAG ได้อย่างสมบูรณ์
Level 1
มีเพียงการทดลองเรียก API หรือยังไม่สามารถใช้งานจริง

7. System Integration
Level 5
ทุกองค์ประกอบทำงานเป็นระบบเดียวกัน ตั้งแต่ User → Query Processing → Dense/Graph Retrieval → Hybrid Fusion → LLM → Answer มี Error Handling และ Architecture ที่ชัดเจน
Level 4
องค์ประกอบหลักทำงานร่วมกันได้ครบและมี Workflow ชัดเจน
Level 3
ระบบทำงานครบตามข้อกำหนด แต่ Architecture ยังเป็นพื้นฐาน
Level 2
องค์ประกอบแต่ละส่วนทำงานได้ แต่การเชื่อมต่อระหว่างส่วนยังมีปัญหา
Level 1
เป็น Prototype หลายส่วนที่ยังไม่สามารถทำงานร่วมกันได้

8. Evaluation & Experimental Analysis
Level 5
มีการออกแบบการทดลองอย่างเป็นระบบ เปรียบเทียบ Dense RAG, Graph RAG, Hybrid RAG รวมถึง Local LLM และ API LLM มี Metrics ที่เหมาะสม และสามารถวิเคราะห์สาเหตุของผลลัพธ์ได้
Level 4
มีการทดลองและเปรียบเทียบหลาย Configuration พร้อม Metrics และการวิเคราะห์ผล
Level 3
มี Test Dataset และผลการทดลองพื้นฐาน แต่การวิเคราะห์ยังไม่ลึก
Level 2
มีการทดสอบระบบ แต่ไม่มีการเปรียบเทียบหรือ Metrics ที่ชัดเจน
Level 1
แสดงเพียงตัวอย่างคำตอบหรือ Demo โดยไม่มีการประเมินผลอย่างเป็นระบบ

9. ระดับคุณภาพของ Project โดยรวม
เพื่อให้การตัดสินระดับ Project มีความชัดเจน สามารถใช้หลักดังนี้
ระดับ
เกณฑ์พิจารณาโดยรวม
Level 5
ทุกองค์ประกอบทำงานจริง มี Hybrid RAG ที่สมบูรณ์ มี Evaluation และสามารถวิเคราะห์ผลเชิงลึก
Level 4
องค์ประกอบหลักครบและทำงานร่วมกันได้ดี มีการทดลองและวิเคราะห์ผล
Level 3
ระบบครบตามข้อกำหนดและทำงานได้ แต่เป็นการ Implementation ในระดับพื้นฐาน
Level 2
ทำได้บางองค์ประกอบ แต่ยังขาดการบูรณาการหรือมีส่วนสำคัญที่ทำงานไม่สมบูรณ์
Level 1
เป็น Prototype หรือ Demo บางส่วน และไม่สามารถแสดงการทำงานของระบบตามข้อกำหนดได้ครบ


หลักการสำคัญในการให้คะแนน
การมี Technology ไม่เท่ากับการได้ระดับคุณภาพสูง
ตัวอย่างเช่น
มี Neo4j → ไม่ได้หมายความว่า Graph RAG อยู่ในระดับสูง
มี Vector Database → ไม่ได้หมายความว่า Dense RAG มีคุณภาพสูง
เรียก OpenAI API ได้ → ไม่ได้หมายความว่า API LLM Integration อยู่ในระดับสูง
มีทั้ง Vector + Graph → ไม่ได้หมายความว่าเป็น Hybrid RAG ระดับสูง
ระดับคุณภาพจะพิจารณาจาก
“สามารถนำเทคโนโลยีมาแก้ปัญหาได้จริง และสามารถแสดงหลักฐานจากการทดลองว่าระบบทำงานอย่างมีประสิทธิภาพเพียงใด”

ตัวอย่างการแยกระดับ Project
Project A — Level 1
มี Vector Database, Neo4j และ Ollama แต่แต่ละส่วนทำงานแยกกัน ไม่มี Hybrid RAG และไม่มีผลการทดลอง
Project B — Level 2
มี Dense RAG และ Graph RAG ทำงานได้ แต่ใช้แยกกัน และยังไม่มีการเปรียบเทียบผลอย่างเป็นระบบ
Project C — Level 3
มี Dense RAG + Graph RAG + Hybrid RAG + Local LLM + API LLM ทำงานครบ แต่ใช้วิธี Fusion พื้นฐาน และมี Evaluation เพียงเบื้องต้น
Project D — Level 4
องค์ประกอบครบ ทำงานร่วมกันจริง มีการปรับ Retrieval / Fusion และมีการทดลองเปรียบเทียบ Dense, Graph และ Hybrid รวมถึง Local และ API LLM
Project E — Level 5
ระบบครบทุกองค์ประกอบ มี Architecture ที่เหมาะสม มี Hybrid Retrieval ที่ออกแบบอย่างเป็นระบบ มีการทดลองหลาย Configuration มี Metrics ที่เหมาะสม และสามารถวิเคราะห์ได้ว่า เหตุใดวิธีหนึ่งจึงให้ผลแตกต่างจากอีกวิธีหนึ่ง

ข้อเสนอแนะสำหรับการกำหนดคะแนน
หากต้องการใช้เป็นคะแนน Final Project 100 คะแนน สามารถกำหนดเป็น
ด้านประเมิน
คะแนน
Data & Knowledge Base
10
Dense RAG
15
Graph RAG
15
Hybrid RAG
20
Local LLM + API LLM
15
System Integration
10
Evaluation & Analysis
10
Documentation / Presentation
5
รวม
100

จากนั้นแต่ละด้านให้ Level 1–5 แล้วแปลงเป็นคะแนนของด้านนั้น
ตัวอย่างเช่น Hybrid RAG = 20 คะแนน
Level 5 → 17–20
Level 4 → 13–16
Level 3 → 9–12
Level 2 → 5–8
Level 1 → 0–4

