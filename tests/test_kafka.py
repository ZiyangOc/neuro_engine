from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'tasks',
    bootstrap_servers=['localhost:9092'],
    auto_offset_reset='earliest',
    enable_auto_commit=False,  # 禁止自动提交偏移量
    group_id='task-checker',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

messages = consumer.poll(timeout_ms=1000, max_records=1)  # 检查是否有消息

if messages:
    for partition, records in messages.items():
        if records:
            print("Task exists:")
            #你可以打印records中第一个消息。例如：
            print (records[0].value)
            #如果要获取消息的offset
            print (records[0].offset)
            #如果要获取消息的key
            print (records[0].key)
            break
else:
    print("No task found in kafka.")

consumer.close()