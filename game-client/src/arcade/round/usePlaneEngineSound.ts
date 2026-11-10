import { useCallback, useEffect, useRef, useState } from 'react';
import type { RoundPhase } from '../types';

interface PlaneEngineAudio {
  context: AudioContext;
  master: GainNode;
  engine: OscillatorNode;
  harmonic: OscillatorNode;
  engineFilter: BiquadFilterNode;
  noise: AudioBufferSourceNode;
  noiseFilter: BiquadFilterNode;
}

function createPlaneEngineAudio(): PlaneEngineAudio {
  const context = new AudioContext();
  const master = context.createGain();
  master.gain.value = 0;
  master.connect(context.destination);

  const engineFilter = context.createBiquadFilter();
  engineFilter.type = 'lowpass';
  engineFilter.frequency.value = 420;
  engineFilter.Q.value = 0.7;
  engineFilter.connect(master);

  const engine = context.createOscillator();
  engine.type = 'sawtooth';
  engine.frequency.value = 58;
  engine.connect(engineFilter);
  engine.start();

  const harmonic = context.createOscillator();
  const harmonicGain = context.createGain();
  harmonic.type = 'triangle';
  harmonic.frequency.value = 116;
  harmonicGain.gain.value = 0.24;
  harmonic.connect(harmonicGain);
  harmonicGain.connect(engineFilter);
  harmonic.start();

  const noiseBuffer = context.createBuffer(
    1,
    context.sampleRate * 2,
    context.sampleRate,
  );
  const noiseSamples = noiseBuffer.getChannelData(0);
  for (let i = 0; i < noiseSamples.length; i += 1) {
    noiseSamples[i] = Math.random() * 2 - 1;
  }

  const noise = context.createBufferSource();
  const noiseFilter = context.createBiquadFilter();
  const noiseGain = context.createGain();
  noise.buffer = noiseBuffer;
  noise.loop = true;
  noiseFilter.type = 'bandpass';
  noiseFilter.frequency.value = 360;
  noiseFilter.Q.value = 0.55;
  noiseGain.gain.value = 0.22;
  noise.connect(noiseFilter);
  noiseFilter.connect(noiseGain);
  noiseGain.connect(master);
  noise.start();

  return {
    context,
    master,
    engine,
    harmonic,
    engineFilter,
    noise,
    noiseFilter,
  };
}

export function usePlaneEngineSound(
  phase: RoundPhase,
  multiplier: number,
) {
  const [enabled, setEnabled] = useState(true);
  const stateRef = useRef({ phase, multiplier, enabled });
  const audioRef = useRef<PlaneEngineAudio | null>(null);

  useEffect(() => {
    stateRef.current = { phase, multiplier, enabled };
  }, [enabled, multiplier, phase]);

  const updateSound = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const { phase: currentPhase, multiplier: currentMultiplier, enabled: isEnabled } =
      stateRef.current;
    const flying = isEnabled && currentPhase === 'flying';
    const safeMultiplier = Math.max(1, currentMultiplier);
    const rise = Math.min(Math.log2(safeMultiplier), 5);
    const now = audio.context.currentTime;

    audio.master.gain.setTargetAtTime(
      flying ? 0.035 + rise * 0.009 : 0,
      now,
      flying ? 0.22 : 0.12,
    );
    audio.engine.frequency.setTargetAtTime(58 + rise * 19, now, 0.18);
    audio.harmonic.frequency.setTargetAtTime(116 + rise * 38, now, 0.18);
    audio.engineFilter.frequency.setTargetAtTime(420 + rise * 150, now, 0.2);
    audio.noiseFilter.frequency.setTargetAtTime(360 + rise * 125, now, 0.2);
  }, []);

  const unlockAudio = useCallback(() => {
    if (!audioRef.current) {
      try {
        audioRef.current = createPlaneEngineAudio();
      } catch (error) {
        console.error('Could not initialize plane engine audio:', error);
        return;
      }
    }

    void audioRef.current.context.resume().then(updateSound).catch((error: unknown) => {
      console.error('Could not start plane engine audio:', error);
    });
  }, [updateSound]);

  useEffect(() => {
    const onUserGesture = () => {
      if (audioRef.current) return;
      unlockAudio();
      if (audioRef.current) {
        window.removeEventListener('pointerdown', onUserGesture);
        window.removeEventListener('keydown', onUserGesture);
      }
    };

    window.addEventListener('pointerdown', onUserGesture);
    window.addEventListener('keydown', onUserGesture);

    return () => {
      window.removeEventListener('pointerdown', onUserGesture);
      window.removeEventListener('keydown', onUserGesture);
      const audio = audioRef.current;
      audioRef.current = null;
      if (audio) void audio.context.close();
    };
  }, [unlockAudio]);

  useEffect(() => {
    updateSound();
  }, [enabled, phase, multiplier, updateSound]);

  const toggle = useCallback(() => {
    setEnabled((current) => !current);
  }, []);

  return { enabled, toggle };
}
