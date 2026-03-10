#!/bin/bash
# test_quick.sh
# Tests the /quick endpoint with a simulated user input.

TEXT=${1:-"¿Qué hora es?"}
USER_ID=${2:-"test_quick_user"}

echo "Sending to /quick: \"$TEXT\""
echo "--- Streaming Response ---"

curl -X POST http://localhost:8000/quick \
  -H "Content-Type: application/json" \
  -H "x-client-key: quick_test_key" \
  -d "{\"text\": \"$TEXT\", \"user_id\": \"$USER_ID\"}" \
  -N

echo -e "\n--------------------------"
