import React, { useState, useEffect } from 'react';
import * as Tone from 'tone';
import { Play, Square, Cpu, MoreHorizontal, Settings, Volume2 } from 'lucide-react';
import { motion } from 'framer-motion';

const STEPS = 16;
const INSTRUMENTS = [
    { id: 'kick', name: 'SOLID_KICK', color: '#00f2ff', accent: 'cyan' },
    { id: 'snare', name: 'CRISP_SNARE', color: '#ff0055', accent: 'pink' },
    { id: 'hihat', name: 'METALLIC_HAT', color: '#9d00ff', accent: 'purple' },
    { id: 'clap', name: 'ROOM_CLAP', color: '#00ff88', accent: 'green' },
];

const Sequencer = () => {
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentStep, setCurrentStep] = useState(0);
    const [bpm, setBpm] = useState(128);
    const [grid, setGrid] = useState(
        INSTRUMENTS.reduce((acc, inst) => ({ ...acc, [inst.id]: Array(STEPS).fill(false) }), {})
    );

    useEffect(() => {
        const players = new Tone.Players({
            kick: "https://tonejs.github.io/audio/drum-samples/kick.mp3",
            snare: "https://tonejs.github.io/audio/drum-samples/snare.mp3",
            hihat: "https://tonejs.github.io/audio/drum-samples/hihat.mp3",
            clap: "https://tonejs.github.io/audio/drum-samples/clap.mp3",
        }).toDestination();

        const loop = new Tone.Sequence(
            (time, step) => {
                setCurrentStep(step);
                INSTRUMENTS.forEach(inst => {
                    if (grid[inst.id][step]) players.player(inst.id).start(time);
                });
            },
            Array.from({ length: STEPS }, (_, i) => i),
            "16n"
        ).start(0);

        Tone.Transport.bpm.value = bpm;
        if (isPlaying) Tone.Transport.start();
        else Tone.Transport.stop();

        return () => {
            loop.dispose();
            players.dispose();
        };
    }, [isPlaying, grid, bpm]);

    return (
        <div className="flex flex-col h-full gap-8 animate-in fade-in slide-in-from-bottom-8 duration-1000 content-centered py-12">
            <div className="flex flex-col gap-2">
                <h2 className="text-4xl font-black tracking-tighter text-white">Drum Labs.</h2>
                <p className="text-zinc-500 max-w-lg font-medium">Precision rhythm engineering with AI-assisted pattern generation.</p>
            </div>

            <div className="glass-panel border-beam p-10 flex flex-col gap-10 fluor-shadow-purple relative">
                <div className="flex items-center justify-between">
                    <div className="flex gap-8 items-center">
                        <button
                            onClick={() => setIsPlaying(!isPlaying)}
                            className={`w-16 h-16 rounded-3xl flex items-center justify-center transition-all duration-500 ${isPlaying ? 'bg-white text-black shadow-[0_0_40px_rgba(255,255,255,0.2)]' : 'bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-white'
                                }`}
                        >
                            {isPlaying ? <Square size={24} fill="currentColor" /> : <Play size={24} fill="currentColor" className="ml-1" />}
                        </button>

                        <div className="flex flex-col gap-1">
                            <label className="label-pro text-[9px]">Master Tempo</label>
                            <div className="flex items-baseline gap-2">
                                <input
                                    type="number"
                                    value={bpm}
                                    onChange={e => setBpm(Number(e.target.value))}
                                    className="bg-transparent text-3xl font-black font-mono text-white outline-none w-24 tracking-tighter"
                                />
                                <span className="text-xs font-bold text-zinc-600">BPM</span>
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-4">
                        <button className="btn-premium btn-ghost gap-2 h-14 px-8">
                            <Cpu size={18} className="text-[#9d00ff]" />
                            AI Imagine
                        </button>
                        <button className="btn-premium btn-ghost h-14 w-14">
                            <Settings size={20} className="text-zinc-500" />
                        </button>
                    </div>
                </div>

                <div className="flex flex-col gap-3">
                    {INSTRUMENTS.map((inst) => (
                        <div key={inst.id} className="flex items-center gap-6 group">
                            <div className="w-32 flex flex-col items-end opacity-40 group-hover:opacity-100 transition-opacity">
                                <span className="text-[10px] font-black tracking-widest text-zinc-500">{inst.id.toUpperCase()}</span>
                                <span className="text-[9px] font-bold text-zinc-700 -mt-1 font-mono">{inst.name}</span>
                            </div>

                            <div className="flex-1 flex gap-2">
                                {grid[inst.id].map((active, i) => (
                                    <motion.div
                                        key={i}
                                        whileHover={{ scale: 1.05 }}
                                        whileTap={{ scale: 0.95 }}
                                        onClick={() => {
                                            const newGrid = { ...grid };
                                            newGrid[inst.id][i] = !newGrid[inst.id][i];
                                            setGrid(newGrid);
                                        }}
                                        className={`h-12 flex-1 rounded-xl cursor-pointer transition-all duration-300 relative overflow-hidden flex items-center justify-center ${i % 4 === 0 ? 'bg-white/5' : 'bg-white/[0.02]'
                                            } ${active ? 'z-10' : ''}`}
                                    >
                                        {active && (
                                            <motion.div
                                                initial={{ opacity: 0, scale: 0.5 }}
                                                animate={{ opacity: 1, scale: 1 }}
                                                className="absolute inset-1.5 rounded-lg shadow-lg"
                                                style={{
                                                    background: `linear-gradient(135deg, ${inst.color}, #fff)`,
                                                    boxShadow: `0 0 20px ${inst.color}88`
                                                }}
                                            />
                                        )}
                                        {currentStep === i && (
                                            <div className="absolute inset-0 bg-white/10 pointer-events-none" />
                                        )}
                                        {/* Subtle grid lines */}
                                        <div className="w-[1px] h-3 bg-white/5 absolute left-0" />
                                    </motion.div>
                                ))}
                            </div>

                            <div className="w-12 flex justify-center opacity-0 group-hover:opacity-40 transition-opacity">
                                <Volume2 size={16} className="text-zinc-500" />
                            </div>
                        </div>
                    ))}
                </div>

                {/* Timeline dots */}
                <div className="flex gap-2 ml-32 pr-12">
                    {Array.from({ length: STEPS }).map((_, i) => (
                        <div key={i} className={`flex-1 flex justify-center transition-colors duration-300 ${currentStep === i ? 'text-white' : 'text-zinc-800'}`}>
                            <div className={`w-1 h-1 rounded-full ${currentStep === i ? 'bg-white' : 'bg-current'}`} />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default Sequencer;
