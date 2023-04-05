brief:
cache translated sentences in mongodb and query them first
split sentences at . or ,

 kubectl create secret generic openai --from-literal=OPENAI_API_KEY="sk-" -n translator