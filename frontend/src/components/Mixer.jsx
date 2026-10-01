import React, { useState } from 'react';
import { Volume2, VolumeX, Settings, MoreVertical, Sliders, Activity } from 'lucide-react';
import { motion } from 'framer-motion';

const Channel = ({ name, type, color }) => {
    const [volume, setVolume] = useState(0.8);
    const [isMuted, setIsMuted] = useState(false);

    return (
        <div className="w-32 flex flex-col items-center gap-6 py-6 group relative border-r border-white/5 last:border-none">
            <div className="flex flex-col items-center">
                <span className="label-pro text-[8px] opacity-40 mb-1">{type}</span>
                <span className="text-[10px] font-black tracking-tight text-white uppercase whitespace-nowrap overflow-hidden text-center w-full px-2">
                    {name}
                </span>
            </div>

            <div className="relative h-[300px] w-12 bg-black/40 rounded-2xl flex items-center justify-center p-2 shadow-inner border border-white/5 overflow-hidden">
                {/* DB Indicators */}
                <div className="absolute inset-0 flex flex-col justify-between py-6 px-1 opacity-10 pointer-events-none">
                    {[0, -6, -12, -18, -24, -30, -36].map(db => (
                        <span key={db} className="text-[8px] font-mono font-bold text-white leading-none">{db}</span>
                    ))}
                </div>

                {/* Meter */}
                <div className="h-full w-1.5 bg-zinc-900 rounded-full flex flex-col-reverse overflow-hidden absolute left-2">
                    <motion.div
                        animate={{ height: isMuted ? '0%' : `${volume * 100}%` }}
                        className="w-full shadow-[0_0_15px_rgba(255,255,255,0.2)]"
                        style={{ background: `linear-gradient(to top, ${color}, #fff)` }}
                    />
                </div>

                {/* Fader Track Inner */}
                <div className="relative h-full w-[2px] bg-white/5" />

                {/* Premium Fader Knob */}
                <motion.div
                    className="absolute w-10 h-16 bg-[#18181b] border border-white/20 rounded-xl shadow-2xl flex flex-col items-center justify-center z-20 cursor-grab active:cursor-grabbing border-beam"
                    style={{ bottom: `calc(${volume * 100}% - 32px)` }}
                    drag="y"
                    dragConstraints={{ top: -240, bottom: 0 }}
                    onDrag={(e, info) => {
                        const bbox = e.target.parentElement.getBoundingClientRect();
                        const newVol = Math.max(0, Math.min(1, 1 - (info.point.y - bbox.top) / 240));
                        setVolume(newVol);
                    }}
                >
                    <div className={`w-full h-1 shadow-[0_0_10px_currentColor] my-auto`} style={{ color: color, backgroundColor: 'currentColor' }} />
                    <span className="text-[8px] font-mono font-bold text-zinc-500 mb-2">{(volume * 100).toFixed(0)}</span>
                </motion.div>
            </div>

            <div className="flex gap-2 w-full px-4">
                <button
                    onClick={() => setIsMuted(!isMuted)}
                    className={`flex-1 h-10 rounded-xl border font-bold text-[10px] transition-all flex items-center justify-center ${isMuted ? 'bg-red-500/10 border-red-500/40 text-red-500' : 'bg-white/5 border-white/5 text-zinc-600 hover:text-white hover:border-white/10'
                        }`}
                >
                    M
                </button>
                <button className="flex-1 h-10 rounded-xl bg-white/5 border border-white/5 text-zinc-600 hover:text-white hover:border-white/10 font-bold text-[10px] flex items-center justify-center">
                    S
                </button>
            </div>

            <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center hover:bg-white/10 transition-colors cursor-pointer group-hover:scale-110 duration-500">
                <MoreVertical size={16} className="text-zinc-700" />
            </div>
        </div>
    );
};

const Mixer = () => {
    return (
        <div className="flex flex-col h-full gap-8 animate-in fade-in slide-in-from-bottom-8 duration-1000 content-centered py-12">
            <div className="flex items-center justify-between">
                <div className="flex flex-col gap-2">
                    <h2 className="text-4xl font-black tracking-tighter text-white">Master Console.</h2>
                    <p className="text-zinc-500 max-w-lg font-medium">Precision audio routing and signal processing architecture.</p>
                </div>

                <div className="flex gap-6 items-center">
                    <div className="flex flex-col items-end">
                        <span className="label-pro text-[9px]">Peak Level</span>
                        <div className="flex items-center gap-2">
                            <Activity size={16} className="text-[#00ff88]" />
                            <span className="text-xl font-bold font-mono text-white tracking-widest">-2.4dB</span>
                        </div>
                    </div>
                    <button className="btn-premium btn-ghost h-14 w-14">
                        <Settings size={20} className="text-zinc-500" />
                    </button>
                </div>
            </div>

            <div className="flex-1 glass-panel border-beam p-6 flex flex-col fluor-shadow-cyan">
                <div className="flex-1 flex overflow-x-auto min-h-0 bg-black/20 rounded-xl border border-white/5 shadow-inner">
                    <Channel name="KICK_IN" type="INPUT_1" color="#00f2ff" />
                    <Channel name="VOCAL_MOD" type="VOICE_A" color="#9d00ff" />
                    <Channel name="SYNTH_L" type="COMP_B" color="#ff0055" />
                    <Channel name="BASS_SUB" type="LOW_END" color="#00ff88" />
                    <Channel name="FX_SEND" type="RTN_1" color="#f2ff00" />
                    <Channel name="AMBIENCE" type="BUS_A" color="#ff8800" />

                    <div className="flex-1 bg-black/10" />

                    {/* Master Channel */}
                    <div className="w-[180px] bg-white/5 border-l border-white/10 flex flex-col items-center py-6 shadow-2xl z-30 relative overflow-hidden backdrop-blur-3xl">
                        <div className="absolute top-0 right-0 p-4 opacity-5">
                            <Sliders size={120} />
                        </div>

                        <div className="flex flex-col items-center mb-8 relative">
                            <span className="label-pro text-accent-fluor">MASTER_MAIN</span>
                            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mt-1">Stereo Mix Out</span>
                        </div>

                        <div className="relative h-[300px] w-20 flex justify-center gap-2">
                            {/* Master Stereo Meters */}
                            <div className="h-full w-2 bg-black rounded-full overflow-hidden flex flex-col-reverse p-[1.5px]">
                                <div className="w-full bg-[#00ff88] rounded-full h-3/4 shadow-[0_0_10px_#00ff88]" />
                            </div>
                            <div className="h-full w-2 bg-black rounded-full overflow-hidden flex flex-col-reverse p-[1.5px]">
                                <div className="w-full bg-[#00ff88] rounded-full h-[68%] shadow-[0_0_10px_#00ff88]" />
                            </div>

                            <div className="w-[1px] h-full bg-white/5 mx-2" />

                            {/* Master Fader */}
                            <motion.div
                                className="absolute w-14 h-20 bg-zinc-900 border border-white/10 rounded-2xl shadow-[0_20px_40px_rgba(0,0,0,0.8)] flex flex-col items-center justify-center z-40 border-beam transition-transform"
                                style={{ bottom: '25%' }}
                                whileHover={{ scale: 1.05 }}
                            >
                                <div className="w-full h-1.5 bg-accent-fluor shadow-[0_0_15px_#00f2ff] my-auto" />
                                <div className="flex flex-col items-center mb-1">
                                    <span className="text-[9px] font-black text-white leading-none">0.0</span>
                                    <span className="text-[7px] font-bold text-zinc-600">dB</span>
                                </div>
                            </motion.div>
                        </div>

                        <div className="mt-auto px-6 w-full space-y-4">
                            <div className="flex items-center justify-between">
                                <span className="text-[10px] font-bold text-zinc-500 uppercase">Stereo Width</span>
                                <span className="text-[10px] font-bold text-white">120%</span>
                            </div>
                            <div className="w-full h-1 bg-black rounded-full overflow-hidden">
                                <div className="h-full bg-white/20 w-3/4" />
                            </div>
                            <button className="w-full btn-premium btn-ghost h-12 text-[10px] font-black border-[#00ff88]/20 text-[#00ff88]">
                                LIMITER_ON
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Mixer;
