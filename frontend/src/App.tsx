import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { WorldEditorPage } from "./pages/WorldEditorPage";
import { WorldsListPage } from "./pages/WorldsListPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/worlds" element={<WorldsListPage />} />
        <Route path="/worlds/new" element={<WorldEditorPage create />} />
        <Route path="/worlds/:worldId" element={<WorldEditorPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
