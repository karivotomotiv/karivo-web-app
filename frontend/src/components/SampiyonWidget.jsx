import { useState, useRef, useEffect } from "react";
import { api, API, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles, X, Send, Mic, MicOff, Volume2, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function SampiyonWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Selam patron, ben Şampiyon 🏆 — Karivo'nun yardımcısıyım. '205/55 R16 kaç tane kaldı?', 'bugün ne sattık?' gibi sor ya da bir işlem yaptır. Mikrofona basıp sesli de konuşabilirsin." },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [ttsLoading, setTtsLoading] = useState(null); // index of message
  const audioRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, open]);

  const send = async (text, historyOverride, autoSpeak = false) => {
    const content = (text ?? input).trim();
    if (!content || sending) return;
    const newMessages = [...messages, { role: "user", content }];
    setMessages(newMessages);
    setInput("");
    setSending(true);
    try {
      const history = (historyOverride ?? newMessages.slice(0, -1))
        .filter((m) => !m.error && (m.role === "user" || m.role === "assistant"))
        .slice(-10)
        .map((m) => ({ role: m.role, content: m.content }));
      const { data } = await api.post("/sampiyon/chat", { message: content, history }, { timeout: 120000 });
      const replyMsg = { role: "assistant", content: data.reply || "(boş yanıt)", tool_trace: data.tool_trace };
      const finalMessages = [...newMessages, replyMsg];
      setMessages(finalMessages);
      if (autoSpeak && replyMsg.content && !replyMsg.content.startsWith("Hata:")) {
        speak(replyMsg.content, finalMessages.length - 1);
      }
    } catch (e) {
      setMessages([...newMessages, { role: "assistant", content: `Hata: ${extractError(e)}`, error: true }]);
    } finally {
      setSending(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      mediaRecorderRef.current = mr;
      audioChunksRef.current = [];
      const historySnapshot = messages;
      mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        setTranscribing(true);
        try {
          const fd = new FormData();
          fd.append("file", blob, "voice.webm");
          const { data } = await api.post("/sampiyon/transcribe", fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 60000 });
          const txt = (data.text || "").trim();
          if (txt) { setInput(txt); send(txt, historySnapshot, true); }
          else toast.info("Ses algılanamadı");
        } catch (e) { toast.error(extractError(e)); }
        finally { setTranscribing(false); }
      };
      mr.start();
      setRecording(true);
    } catch (e) {
      toast.error("Mikrofon izni gerekli");
    }
  };
  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
    }
  };

  const speak = async (text, idx) => {
    if (ttsLoading !== null) return;
    setTtsLoading(idx);
    try {
      const token = localStorage.getItem("ks_token");
      const resp = await fetch(`${API}/sampiyon/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ text, voice: "onyx", speed: 1.15 }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.src = url;
        await audioRef.current.play().catch(() => toast.info("Otomatik oynatma engellendi — 'Oku'ya basın"));
      }
    } catch (e) {
      toast.error("Ses oynatılamadı");
    } finally {
      setTtsLoading(null);
    }
  };

  return (
    <>
      <audio ref={audioRef} className="hidden" />
      {/* Floating button */}
      <button
        onClick={() => setOpen(!open)}
        className={`fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-xl flex items-center justify-center transition-all ${
          open ? "bg-slate-700 hover:bg-slate-800 scale-90" : "bg-gradient-to-br from-indigo-600 to-fuchsia-600 hover:from-indigo-700 hover:to-fuchsia-700 hover:scale-110"
        } text-white`}
        data-testid="sampiyon-fab"
        title="Şampiyon AI Asistan"
      >
        {open ? <X className="w-6 h-6" /> : <Sparkles className="w-6 h-6" />}
      </button>

      {/* Panel */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 w-[400px] max-w-[calc(100vw-3rem)] h-[600px] max-h-[calc(100vh-8rem)] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden" data-testid="sampiyon-panel">
          {/* Header */}
          <div className="bg-gradient-to-r from-indigo-600 to-fuchsia-600 text-white px-4 py-3 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center backdrop-blur-sm">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="font-extrabold text-sm">Şampiyon</div>
              <div className="text-[11px] text-white/80">Karivo AI Asistanı · Claude Sonnet 5.5</div>
            </div>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`} data-testid={`sampiyon-msg-${i}`}>
                <div className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm ${
                  m.role === "user" ? "bg-slate-900 text-white rounded-br-md"
                  : m.error ? "bg-rose-50 text-rose-800 border border-rose-200 rounded-bl-md"
                  : "bg-white text-slate-900 border border-slate-200 rounded-bl-md shadow-sm"
                }`}>
                  <div className="whitespace-pre-wrap">{m.content}</div>
                  {m.role === "assistant" && !m.error && (
                    <div className="mt-1.5 flex items-center gap-2">
                      <button
                        onClick={() => speak(m.content, i)}
                        disabled={ttsLoading !== null}
                        className="text-xs text-slate-500 hover:text-indigo-700 inline-flex items-center gap-1"
                        data-testid={`sampiyon-speak-${i}`}
                      >
                        {ttsLoading === i ? <Loader2 className="w-3 h-3 animate-spin" /> : <Volume2 className="w-3 h-3" />}
                        Oku
                      </button>
                      {m.tool_trace?.length > 0 && (
                        <span className="text-[10px] text-slate-400">🔧 {m.tool_trace.length} araç kullandı</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-md px-3.5 py-2 shadow-sm">
                  <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
                </div>
              </div>
            )}
            {transcribing && (
              <div className="text-xs text-indigo-600 text-center">🎙️ Ses yazıya çevriliyor...</div>
            )}
          </div>

          {/* Input */}
          <div className="p-3 border-t border-slate-200 bg-white">
            <form onSubmit={(e) => { e.preventDefault(); send(); }} className="flex gap-2">
              <button
                type="button"
                onClick={recording ? stopRecording : startRecording}
                disabled={transcribing || sending}
                className={`w-10 h-10 shrink-0 rounded-xl flex items-center justify-center transition-colors ${
                  recording ? "bg-rose-600 text-white animate-pulse" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
                data-testid="sampiyon-mic"
                title={recording ? "Dinlemeyi bitir" : "Sesli komut"}
              >
                {recording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Şampiyon'a yaz veya mikrofona bas..."
                disabled={sending || recording}
                className="flex-1"
                data-testid="sampiyon-input"
              />
              <Button type="submit" disabled={!input.trim() || sending} className="bg-slate-900 hover:bg-slate-800" data-testid="sampiyon-send">
                <Send className="w-4 h-4" />
              </Button>
            </form>
            <div className="text-[10px] text-slate-400 mt-1.5 text-center">
              AI yanıtlarını daima doğrulayın · Değişiklikler onay ister
            </div>
          </div>
        </div>
      )}
    </>
  );
}
