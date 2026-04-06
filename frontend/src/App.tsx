import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { ExplorePage } from "./pages/ExplorePage";
import { MyPage } from "./pages/MyPage";
import { PlayPage } from "./pages/PlayPage";
import { WorldEditorPage } from "./pages/WorldEditorPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/explore" element={<ExplorePage />} />
        <Route path="/my" element={<MyPage />} />
        <Route path="/worlds" element={<Navigate to="/my" replace />} />
        <Route path="/play" element={<Navigate to="/my" replace />} />
        <Route path="/worlds/new" element={<WorldEditorPage create />} />
        <Route path="/worlds/:worldId" element={<WorldEditorPage />} />
        <Route path="/play/:sessionId" element={<PlayPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
