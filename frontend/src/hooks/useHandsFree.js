import { useEffect, useRef, useState } from "react";

const SILENCE_MS = 1200;
const MIN_SPEECH_MS = 350;
const ONSET_MS = 120;
const MAX_IDLE_MS = 15000;

// Sürekli dinleme: ses seviyesi ile konuşma başı/sonu algılar, bitince blob'u onUtterance'a verir.
export function useHandsFree({ enabled, paused, assistantSpeaking, onSpeechStart, onUtterance, onError }) {
  const [level, setLevel] = useState(0);
  const [userSpeaking, setUserSpeaking] = useState(false);
  const cb = useRef({});
  cb.current = { paused, assistantSpeaking, onSpeechStart, onUtterance, onError };

  useEffect(() => {
    if (!enabled) return undefined;
    let stream, ctx, recorder, timer, cancelled = false;
    let chunks = [], noise = 0.01, speechStart = 0, lastLoud = 0, onsetSince = 0, recStart = 0, inSpeech = false;

    const startRecorder = () => {
      chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      recorder.start();
      recStart = Date.now();
    };
    const finishRecorder = (keep) => {
      const r = recorder;
      if (!r || r.state === "inactive") return;
      r.onstop = () => {
        const blob = new Blob(chunks, { type: "audio/webm" });
        if (keep && !cancelled) cb.current.onUtterance(blob);
        if (!cancelled) startRecorder();
      };
      r.stop();
    };

    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        ctx = new (window.AudioContext || window.webkitAudioContext)();
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 1024;
        ctx.createMediaStreamSource(stream).connect(analyser);
        const buf = new Float32Array(analyser.fftSize);
        startRecorder();

        timer = setInterval(() => {
          analyser.getFloatTimeDomainData(buf);
          let sum = 0;
          for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
          const rms = Math.sqrt(sum / buf.length);
          setLevel(Math.min(1, rms * 12));
          const now = Date.now();
          const { paused: isPaused, assistantSpeaking: aiTalking } = cb.current;
          if (!inSpeech) noise = noise * 0.97 + rms * 0.03;
          const threshold = Math.max(0.015, noise * 2.5) * (aiTalking ? 1.8 : 1);
          const loud = rms > threshold;

          if (isPaused) {
            if (inSpeech) { inSpeech = false; setUserSpeaking(false); }
            onsetSince = 0;
            if (now - recStart > 2000) finishRecorder(false);
            return;
          }
          if (!inSpeech) {
            if (loud) {
              if (!onsetSince) onsetSince = now;
              if (now - onsetSince >= ONSET_MS) {
                inSpeech = true; speechStart = onsetSince; lastLoud = now;
                setUserSpeaking(true);
                cb.current.onSpeechStart?.();
              }
            } else {
              onsetSince = 0;
              if (now - recStart > MAX_IDLE_MS) finishRecorder(false);
            }
          } else {
            if (loud) lastLoud = now;
            else if (now - lastLoud > SILENCE_MS) {
              inSpeech = false; onsetSince = 0;
              setUserSpeaking(false);
              finishRecorder(lastLoud - speechStart >= MIN_SPEECH_MS);
            }
          }
        }, 50);
      } catch (e) {
        cb.current.onError?.(e);
      }
    })();

    return () => {
      cancelled = true;
      clearInterval(timer);
      if (recorder && recorder.state !== "inactive") { recorder.onstop = null; recorder.stop(); }
      stream?.getTracks().forEach((t) => t.stop());
      ctx?.close();
      setLevel(0);
      setUserSpeaking(false);
    };
  }, [enabled]);

  return { level, userSpeaking };
}
