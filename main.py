from graphql_app import graphql_app
from fastapi import FastAPI

fastapi_app = FastAPI(title='DBMS')
fastapi_app.add_route("/graphql", graphql_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
