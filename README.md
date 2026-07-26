# FastAPI WebRTC JWT Auth & Direct User Calling Server

This project provides a WebRTC backend with **JWT Bearer Authentication**, **User Registration**, **User Login**, **Protected User Directory**, and **Direct User-to-User Call Signaling** built with **FastAPI**, **PyJWT**, **SQLite**, and **WebSockets**.

---

## 🔐 REST API & JWT Authentication Reference

### 1. User Registration (`POST /api/register`)
- **Request**:
  ```json
  {
    "username": "alice",
    "password": "secretpassword",
    "display_name": "Alice Smith"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "message": "Registration successful!",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
      "id": "a1b2c3d4",
      "username": "alice",
      "display_name": "Alice Smith",
      "is_online": false
    }
  }
  ```

---

### 2. User Login (`POST /api/login`)
- **Request**:
  ```json
  {
    "username": "alice",
    "password": "secretpassword"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "message": "Login successful!",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
      "id": "a1b2c3d4",
      "username": "alice",
      "display_name": "Alice Smith",
      "is_online": true
    }
  }
  ```

---

### 3. List Users (`GET /api/users`) — 🔒 Protected
Returns all registered users **except the currently logged-in user** (so you only see other users to call):
- **Header**: `Authorization: Bearer <your_access_token>`
- **Response**:
  ```json
  {
    "users": [
      {
        "id": "a1b2c3d4",
        "username": "alice",
        "display_name": "Alice Smith",
        "is_online": true
      },
      {
        "id": "e5f6g7h8",
        "username": "bob",
        "display_name": "Bob Jones",
        "is_online": false
      }
    ]
  }
  ```

---

## 🟢 How `is_online` Status Works Dynamic & Real-time

The `is_online` field is **managed automatically by the server** in real time:
- When a user connects to the WebSocket (`WS /ws/user/{user_id}`), `is_online` becomes `true`.
- When the user closes the app or disconnects the WebSocket, `is_online` instantly becomes `false`.
- No manual database toggling or extra API calls are required!

---

## 📱 Flutter Integration Example with JWT Bearer Token

### Fetching Protected User List in Flutter:
```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

Future<List<dynamic>> fetchUsers(String jwtToken) async {
  final response = await http.get(
    Uri.parse('http://<SERVER_IP>:8000/api/users'),
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $jwtToken', // Pass JWT Token here!
    },
  );

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    return data['users'];
  } else {
    throw Exception('Failed to fetch users: ${response.statusCode}');
  }
}
```

---

## 🧪 Testing Swagger UI & Web Client

1. **Swagger UI**: Visit `http://localhost:8000/docs`. Click **Authorize 🔓** at the top right, enter your JWT token, and execute `GET /api/users`.
2. **Web Test Client**: Visit `http://localhost:8000/test`. Logging in automatically retrieves your JWT token and attaches it to all User Directory requests.
