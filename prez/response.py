from fastapi.responses import StreamingResponse


class StreamingTurtleResponse(StreamingResponse):
    media_type = "text/turtle"

    def render(self, content: str) -> bytes:
        return content.encode("utf-8")


class StreamingTurtleAnnotatedResponse(StreamingTurtleResponse):
    media_type = "text/anot+turtle"
