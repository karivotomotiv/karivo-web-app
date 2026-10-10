import { useState, useRef, useEffect, useCallback } from "react";
import { api, API, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles, X, Send, Mic, MicOff, Volume2, VolumeX, Loader2, Wrench, RotateCcw, Radio } from "lucide-react";
import { useHandsFree } from "@/hooks/useHandsFree";
import { toast } from "sonner";

const TOOL_LABELS = {
  search_tires: "Lastiklere bakıyorum", get_stock_summary: "Stok özetini çıkarıyorum", get_finance_summary: "Finansa bakıyorum",
  list_cariler: "Carilere bakıyorum", add_tire: "Lastik ekliyorum", update_tire_stock: "Stoğu güncelliyorum",
  add_income: "Gelir yazıyorum", add_expense: "Gider yazıyorum", list_recent_sales: "Satışlara bakıyorum",
  add_spending: "Harcama giriyorum", add_todo: "Görev ekliyorum", complete_todo: "Görevi güncelliyorum",
  add_cari: "Cari ekliyorum", add_cari_transaction: "Cari hareketi yazıyorum", add_invoice: "Fatura ekliyorum",
  update_tire: "Lastiği güncelliyorum", create_sale: "Satışı hazırlıyorum", list_records: "Kayıtlara bakıyorum",
  delete_record: "Silme işlemi",
};

const cleanForSpeech = (t) =>
  t.replace(/[*_#`>|]/g, "").replace(/\p{Extended_Pictographic}/gu, "").replace(/\s+/g, " ").trim();

const WHISPER_JUNK = /altyaz|abone ol|izlediğiniz için|teşekkürler\.?$|^\W*$/i;

const WELCOME = "Selam patron, ben Şampiyon. Harcama gir, satış yap, cariye ödeme işle, görev ekle — ne dersen yaparım. Yaz ya da mikrofona basıp söyle.";

async function streamChat(body, onEvent) {
  const resp = await fetch(`${API}/sampiyon/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("ks_token")}` },
    body: JSON.stringify(body),
  });
  if (!resp.ok || !resp.body) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop();
    for (const p of parts) {
      const line = p.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)));
    }
  }
}

export default function SampiyonWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([{ role: "assistant", content: WELCOME }]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [toolStatus, setToolStatus] = useState(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [voice, setVoice] = useState(null); // {idx, phase: 'loading'|'playing'}
  const [handsFree, setHandsFree] = useState(false);
  const messagesRef = useRef(messages);
  const audioRef = useRef(null);
  const ttsAbortRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const scrollRef = useRef(null);
  const panelRef = useRef(null);
  const fabRef = useRef(null);

  useEffect(() => { messagesRef.current = messages; }, [messages]);
  useEffect(() => {
    api.get("/sampiyon/history").then(({ data }) => {
      if (data?.length) {
        setMessages(data.map((m) => ({ role: m.role, content: m.content, tool_trace: (m.tool_names || []).map((name) => ({ name })) })));
      }
    }).catch(() => {});
  }, []);
  useEffect(() => { if (!open) setHandsFree(false); }, [open]);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, open, toolStatus]);

  // Panel dışına (boş alana) tıklanınca paneli kapat, konuşma beklemeye geçer
  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (e) => {
      if (panelRef.current?.contains(e.target) || fabRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown, true);
    return () => document.removeEventListener("pointerdown", onPointerDown, true);
  }, [open]);

  const stopSpeaking = useCallback(() => {
    ttsAbortRef.current?.abort();
    ttsAbortRef.current = null;
    const a = audioRef.current;
    if (a) { a.pause(); a.removeAttribute("src"); a.load(); }
    setVoice(null);
  }, []);

  // Kullanıcı herhangi bir şey yaparsa (tıklama / tuş) konuşmayı kes
  useEffect(() => {
    if (!voice) return undefined;
    const handler = () => stopSpeaking();
    const t = setTimeout(() => {
      document.addEventListener("pointerdown", handler, true);
      document.addEventListener("keydown", handler, true);
    }, 0);
    return () => {
      clearTimeout(t);
      document.removeEventListener("pointerdown", handler, true);
      document.removeEventListener("keydown", handler, true);
    };
  }, [voice, stopSpeaking]);

  const speak = async (text, idx) => {
    stopSpeaking();
    const clean = cleanForSpeech(text);
    if (!clean) return;
    const ctrl = new AbortController();
    ttsAbortRef.current = ctrl;
    setVoice({ idx, phase: "loading" });
    try {
      const resp = await fetch(`${API}/sampiyon/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("ks_token")}` },
        body: JSON.stringify({ text: clean }),
        signal: ctrl.signal,
      });
      if (!resp.ok) throw new Error(await resp.text());
      const blob = await resp.blob();
      if (ctrl.signal.aborted) return;
      const a = audioRef.current;
      a.src = URL.createObjectURL(blob);
      a.playbackRate = 1.25;
      a.onended = () => setVoice(null);
      setVoice({ idx, phase: "playing" });
      await a.play().catch(() => { setVoice(null); toast.info("Otomatik oynatma engellendi — 'Oku'ya basın"); });
    } catch (e) {
      if (e.name !== "AbortError") { setVoice(null); toast.error("Ses oynatılamadı"); }
    }
  };

  const updateLast = (patch) =>
    setMessages((prev) => {
      const next = [...prev];
      next[next.length - 1] = { ...next[next.length - 1], ...patch(next[next.length - 1]) };
      return next;
    });

  const send = async (text, autoSpeak = false) => {
    const content = (text ?? input).trim();
    if (!content || sending) return;
    stopSpeaking();
    const assistantIdx = messagesRef.current.length + 1;
    setMessages((prev) => [...prev, { role: "user", content }, { role: "assistant", content: "", streaming: true }]);
    setInput("");
    setSending(true);
    let final = null;
    try {
      await streamChat({ message: content, history: [] }, (ev) => {
        if (ev.type === "delta") { setToolStatus(null); updateLast((m) => ({ content: m.content + ev.content })); }
        else if (ev.type === "tool") setToolStatus(TOOL_LABELS[ev.name] || "Çalışıyorum");
        else if (ev.type === "done") final = ev;
        else if (ev.type === "error") throw new Error(ev.message);
      });
      if (!final) throw new Error("Yanıt yarıda kesildi");
      const reply = final.reply || "Tamamdır.";
      updateLast(() => ({ content: reply, tool_trace: final.tool_trace, streaming: false }));
      if (final.data_changed) window.dispatchEvent(new CustomEvent("karivo:data-changed"));
      if (autoSpeak) speak(reply, assistantIdx);
    } catch (e) {
      updateLast(() => ({ content: `Hata: ${extractError(e)}`, error: true, streaming: false }));
    } finally {
      setSending(false);
      setToolStatus(null);
    }
  };

  const transcribeAndSend = async (blob, handsFreeMode = false) => {
    setTranscribing(true);
    try {
      const fd = new FormData();
      fd.append("file", blob, "voice.webm");
      const { data } = await api.post("/sampiyon/transcribe", fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 60000 });
      const txt = (data.text || "").trim();
      if (txt && !(handsFreeMode && (txt.length < 2 || WHISPER_JUNK.test(txt)))) send(txt, true);
      else if (!handsFreeMode) toast.info("Ses algılanamadı");
    } catch (e) { toast.error(extractError(e)); }
    finally { setTranscribing(false); }
  };

  const { level, userSpeaking } = useHandsFree({
    enabled: handsFree,
    paused: sending || transcribing || recording,
    assistantSpeaking: voice?.phase === "playing",
    onSpeechStart: () => { if (voice) stopSpeaking(); },
    onUtterance: (blob) => transcribeAndSend(blob, true),
    onError: () => { setHandsFree(false); toast.error("Mikrofon izni gerekli"); },
  });

  const newChat = async () => {
    stopSpeaking();
    try { await api.delete("/sampiyon/history"); } catch (e) { toast.error(extractError(e)); return; }
    setMessages([{ role: "assistant", content: WELCOME }]);
  };

  const startRecording = async () => {
    stopSpeaking();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      mediaRecorderRef.current = mr;
      audioChunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        transcribeAndSend(new Blob(audioChunksRef.current, { type: "audio/webm" }));
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

  return (
    <>
      <audio ref={audioRef} className="hidden" data-testid="sampiyon-audio" />
      <button
        ref={fabRef}
        onClick={() => setOpen(!open)}
        className={`fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-xl flex items-center justify-center transition-all ${
          open ? "bg-slate-700 hover:bg-slate-800 scale-90" : "bg-gradient-to-br from-indigo-600 to-fuchsia-600 hover:from-indigo-700 hover:to-fuchsia-700 hover:scale-110"
        } text-white`}
        data-testid="sampiyon-fab"
        title="Şampiyon AI Asistan"
      >
        {open ? <X className="w-6 h-6" /> : <Sparkles className="w-6 h-6" />}
      </button>

      {open && (
        <div ref={panelRef} className="fixed bottom-24 right-6 z-50 w-[400px] max-w-[calc(100vw-3rem)] h-[600px] max-h-[calc(100vh-8rem)] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden" data-testid="sampiyon-panel">
          <div className="bg-gradient-to-r from-indigo-600 to-fuchsia-600 text-white px-4 py-3 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center backdrop-blur-sm">
              <Sparkles className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <div className="font-extrabold text-sm">Şampiyon</div>
              <div className="text-[11px] text-white/80">Karivo AI Asistanı · Gemini 3 Flash</div>
            </div>
            <button onClick={newChat} title="Yeni Sohbet" className="text-xs bg-white/20 hover:bg-white/30 rounded-lg px-2 py-1 inline-flex items-center gap-1" data-testid="sampiyon-new-chat">
              <RotateCcw className="w-3.5 h-3.5" /> Yeni
            </button>
            {voice && (
              <button onClick={stopSpeaking} className="text-xs bg-white/20 hover:bg-white/30 rounded-lg px-2 py-1 inline-flex items-center gap-1" data-testid="sampiyon-stop-voice">
                <VolumeX className="w-3.5 h-3.5" /> Sustur
              </button>
            )}
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50" data-testid="sampiyon-messages">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`} data-testid={`sampiyon-msg-${i}`}>
                <div className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm ${
                  m.role === "user" ? "bg-slate-900 text-white rounded-br-md"
                  : m.error ? "bg-rose-50 text-rose-800 border border-rose-200 rounded-bl-md"
                  : "bg-white text-slate-900 border border-slate-200 rounded-bl-md shadow-sm"
                }`}>
                  {m.streaming && !m.content ? (
                    <div className="flex items-center gap-2 text-indigo-600 text-xs" data-testid="sampiyon-thinking">
                      <Loader2 className="w-4 h-4 animate-spin" /> {toolStatus || "Düşünüyorum"}...
                    </div>
                  ) : (
                    <div className="whitespace-pre-wrap">{m.content}</div>
                  )}
                  {m.role === "assistant" && !m.error && !m.streaming && m.content && (
                    <div className="mt-1.5 flex items-center gap-2">
                      <button
                        onClick={() => (voice?.idx === i ? stopSpeaking() : speak(m.content, i))}
                        className="text-xs text-slate-500 hover:text-indigo-700 inline-flex items-center gap-1"
                        data-testid={`sampiyon-speak-${i}`}
                      >
                        {voice?.idx === i && voice.phase === "loading" ? <Loader2 className="w-3 h-3 animate-spin" />
                          : voice?.idx === i ? <VolumeX className="w-3 h-3" /> : <Volume2 className="w-3 h-3" />}
                        {voice?.idx === i ? "Durdur" : "Oku"}
                      </button>
                      {m.tool_trace?.length > 0 && (
                        <span className="text-[10px] text-slate-400 inline-flex items-center gap-1" data-testid={`sampiyon-tools-${i}`}>
                          <Wrench className="w-3 h-3" /> {m.tool_trace.length} işlem
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {transcribing && (
              <div className="text-xs text-indigo-600 text-center" data-testid="sampiyon-transcribing">Ses yazıya çevriliyor...</div>
            )}
          </div>

          <div className="p-3 border-t border-slate-200 bg-white">
            <button
              type="button"
              onClick={() => setHandsFree((v) => !v)}
              className={`w-full mb-2 rounded-xl px-3 py-2 text-xs font-semibold inline-flex items-center justify-center gap-2 transition-colors ${
                handsFree ? "bg-emerald-600 text-white hover:bg-emerald-700" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
              data-testid="sampiyon-handsfree-toggle"
            >
              <Radio className={`w-4 h-4 ${handsFree ? "animate-pulse" : ""}`} />
              {handsFree
                ? (transcribing ? "Anlıyorum..." : sending ? "Düşünüyorum..." : userSpeaking ? "Seni dinliyorum..." : "Eller serbest açık — konuş, susunca gönderirim")
                : "Eller Serbest Modu Aç"}
              {handsFree && (
                <span className="ml-1 h-1.5 w-16 bg-white/30 rounded-full overflow-hidden" data-testid="sampiyon-handsfree-level">
                  <span className="block h-full bg-white transition-[width] duration-75" style={{ width: `${Math.round(level * 100)}%` }} />
                </span>
              )}
            </button>
            <form onSubmit={(e) => { e.preventDefault(); send(); }} className="flex gap-2">
              <button
                type="button"
                onClick={recording ? stopRecording : startRecording}
                disabled={transcribing || sending || handsFree}
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
                onChange={(e) => { if (voice) stopSpeaking(); setInput(e.target.value); }}
                placeholder="Şampiyon'a yaz veya mikrofona bas..."
                disabled={recording}
                className="flex-1"
                data-testid="sampiyon-input"
              />
              <Button type="submit" disabled={!input.trim() || sending} className="bg-slate-900 hover:bg-slate-800" data-testid="sampiyon-send">
                <Send className="w-4 h-4" />
              </Button>
            </form>
            <div className="text-[10px] text-slate-400 mt-1.5 text-center">
              Satış ve silme işlemleri onay ister · Konuşurken bir şey yaparsan susar
            </div>
          </div>
        </div>
      )}
    </>
  );
}
