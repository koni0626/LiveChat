(function () {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  let audioContext = null;
  let unlocked = false;

  const masterGainValue = 0.18;

  function getContext() {
    if (!AudioContextClass) return null;
    if (!audioContext) {
      audioContext = new AudioContextClass();
    }
    return audioContext;
  }

  function unlock() {
    const context = getContext();
    if (!context) return;
    if (context.state === "suspended") {
      context.resume().catch(() => {});
    }
    unlocked = true;
  }

  function now(context) {
    return context.currentTime + 0.012;
  }

  function envelope(gain, start, peak, duration, release = 0.05) {
    gain.gain.cancelScheduledValues(start);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, peak), start + Math.min(0.025, duration * 0.35));
    gain.gain.exponentialRampToValueAtTime(0.0001, start + Math.max(0.03, duration - release));
  }

  function tone(context, {
    frequency = 440,
    type = "sine",
    start = now(context),
    duration = 0.12,
    gain = 0.14,
    endFrequency = null,
  } = {}) {
    const oscillator = context.createOscillator();
    const gainNode = context.createGain();
    const master = context.createGain();
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(frequency, start);
    if (endFrequency) {
      oscillator.frequency.exponentialRampToValueAtTime(endFrequency, start + duration);
    }
    master.gain.setValueAtTime(masterGainValue, start);
    envelope(gainNode, start, gain, duration);
    oscillator.connect(gainNode);
    gainNode.connect(master);
    master.connect(context.destination);
    oscillator.start(start);
    oscillator.stop(start + duration);
  }

  function chord(context, frequencies, options = {}) {
    const start = options.start || now(context);
    frequencies.forEach((frequency, index) => {
      tone(context, {
        frequency,
        type: options.type || "sine",
        start: start + (options.stagger || 0) * index,
        duration: options.duration || 0.16,
        gain: options.gain || 0.12,
        endFrequency: options.endFrequency ? options.endFrequency[index] : null,
      });
    });
  }

  function sparkle(context, start = now(context)) {
    chord(context, [880, 1320, 1760], { start, stagger: 0.035, duration: 0.13, gain: 0.09 });
  }

  function softThump(context, start = now(context)) {
    tone(context, { frequency: 120, endFrequency: 72, type: "sine", start, duration: 0.16, gain: 0.16 });
  }

  function noiseBurst(context, {
    start = now(context),
    duration = 0.045,
    gain = 0.18,
  } = {}) {
    const sampleRate = context.sampleRate;
    const buffer = context.createBuffer(1, Math.max(1, Math.floor(sampleRate * duration)), sampleRate);
    const data = buffer.getChannelData(0);
    for (let index = 0; index < data.length; index += 1) {
      data[index] = (Math.random() * 2 - 1) * (1 - index / data.length);
    }
    const source = context.createBufferSource();
    const gainNode = context.createGain();
    const master = context.createGain();
    source.buffer = buffer;
    master.gain.setValueAtTime(masterGainValue, start);
    envelope(gainNode, start, gain, duration, 0.018);
    source.connect(gainNode);
    gainNode.connect(master);
    master.connect(context.destination);
    source.start(start);
    source.stop(start + duration);
  }

  const patterns = {
    affinity() {
      const context = getContext();
      if (!context) return;
      const start = now(context);
      tone(context, { frequency: 420, endFrequency: 620, type: "triangle", start, duration: 0.08, gain: 0.12 });
      chord(context, [740, 988], { start: start + 0.045, stagger: 0.04, duration: 0.13, gain: 0.11 });
      tone(context, { frequency: 1480, type: "sine", start: start + 0.15, duration: 0.08, gain: 0.07 });
    },
    affinityMilestone() {
      const context = getContext();
      if (!context) return;
      const start = now(context);
      tone(context, { frequency: 392, endFrequency: 660, type: "triangle", start, duration: 0.1, gain: 0.13 });
      chord(context, [660, 880, 1320], { start: start + 0.055, stagger: 0.055, duration: 0.18, gain: 0.12 });
      chord(context, [988, 1318, 1760], { start: start + 0.24, stagger: 0.045, duration: 0.16, gain: 0.095 });
      sparkle(context, start + 0.39);
    },
    ending() {
      const context = getContext();
      if (!context) return;
      const start = now(context);
      softThump(context, start);
      chord(context, [220, 330, 440], { start: start + 0.08, stagger: 0.08, duration: 0.42, gain: 0.12 });
      chord(context, [660, 880], { start: start + 0.42, stagger: 0.05, duration: 0.32, gain: 0.09 });
    },
    message() {
      const context = getContext();
      if (!context) return;
      chord(context, [740, 980], { duration: 0.09, stagger: 0.035, gain: 0.075 });
    },
    send() {
      const context = getContext();
      if (!context) return;
      const start = now(context);
      tone(context, { frequency: 520, endFrequency: 920, type: "triangle", start, duration: 0.09, gain: 0.14 });
      tone(context, { frequency: 980, endFrequency: 1660, type: "sine", start: start + 0.055, duration: 0.11, gain: 0.1 });
      tone(context, { frequency: 1960, type: "sine", start: start + 0.135, duration: 0.045, gain: 0.06 });
    },
    action() {
      const context = getContext();
      if (!context) return;
      const start = now(context);
      softThump(context, start);
      tone(context, { frequency: 520, endFrequency: 620, start: start + 0.055, duration: 0.14, gain: 0.075 });
    },
    choice() {
      const context = getContext();
      if (!context) return;
      chord(context, [520, 700], { duration: 0.11, stagger: 0.04, gain: 0.085 });
    },
    imageDone() {
      const context = getContext();
      if (!context) return;
      const start = now(context);
      chord(context, [520, 780, 1040], { start, stagger: 0.055, duration: 0.18, gain: 0.095 });
      sparkle(context, start + 0.16);
    },
    itemDone() {
      const context = getContext();
      if (!context) return;
      const start = now(context);
      tone(context, { frequency: 460, endFrequency: 620, start, duration: 0.11, gain: 0.09, type: "triangle" });
      tone(context, { frequency: 760, start: start + 0.09, duration: 0.14, gain: 0.08, type: "sine" });
    },
    move() {
      const context = getContext();
      if (!context) return;
      tone(context, { frequency: 360, endFrequency: 620, type: "triangle", duration: 0.2, gain: 0.075 });
      tone(context, { frequency: 760, start: now(context) + 0.12, duration: 0.1, gain: 0.065 });
    },
    shutter() {
      const context = getContext();
      if (!context) return;
      const start = now(context);
      noiseBurst(context, { start, duration: 0.04, gain: 0.34 });
      tone(context, { frequency: 1900, endFrequency: 1200, type: "square", start: start + 0.006, duration: 0.04, gain: 0.09 });
      noiseBurst(context, { start: start + 0.055, duration: 0.06, gain: 0.24 });
      tone(context, { frequency: 520, endFrequency: 360, type: "triangle", start: start + 0.055, duration: 0.07, gain: 0.1 });
    },
  };

  function play(name) {
    if (!unlocked) return;
    const pattern = patterns[name];
    if (!pattern) return;
    try {
      pattern();
    } catch (error) {
      // Sound must never break chat interaction.
    }
  }

  ["pointerdown", "keydown", "touchstart"].forEach((eventName) => {
    window.addEventListener(eventName, unlock, { once: true, passive: true });
  });

  window.LiveChatSound = {
    play,
    unlock,
  };
})();
