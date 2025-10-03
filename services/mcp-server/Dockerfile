FROM golang:1.25.1-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go env -w GOPROXY=https://proxy.golang.org
RUN go mod download
COPY . .
RUN go build -o /mcp-server ./main.go ./ws_transport.go

FROM alpine:3.18
RUN apk add --no-cache ca-certificates
COPY --from=build /mcp-server /bin/mcp-server
EXPOSE 9001
ENV PORT=9001
ENTRYPOINT ["/bin/mcp-server"]
