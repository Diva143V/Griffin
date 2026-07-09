import React, { useState, useEffect, useRef, Component } from 'react';

// Error Boundary Component
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <div style={{ padding: '20px', color: 'var(--accent-rose)', textAlign: 'center' }}>Something went wrong. Please refresh the page.</div>;
    }
    return this.props.children;
  }
}
import { 
  Compass, BookOpen, Zap, FileText, Search, Shield, Play, 
  Send, Trash2, Settings, Download, AlertTriangle, CheckCircle, 
  Beaker, MessageSquare, Loader, ArrowRight, Info, Activity, 
  Clock, Cpu, Database, Network, Globe, Layers
} from 'lucide-react';

const API_BASE = 'http://localhost:8000';
const WS_BASE = 'ws://localhost:8000';

function App() {
  const [activeTab, setActiveTab] = useState(0);
  const [query, setQuery] = useState('');
  const [email, setEmail] = useState('test@example.com');
  const [scKey, setScKey] = useState('');
  const [googleKey, setGoogleKey] = useState('');
  const [selectedModel, setSelectedModel] = useState('gemma3:4b');
  const [geminiModel, setGeminiModel] = useState('gemini-2.5-flash');
  
  // LLM Options state
  const [llmTemp, setLlmTemp] = useState(0.7);
  const [llmNumCtx, setLlmNumCtx] = useState(8192);
  const [llmThink, setLlmThink] = useState(true);
  
  // Model Routing state
  const [useGlobalModel, setUseGlobalModel] = useState(true);
  const [modelRouting, setModelRouting] = useState({
    planner: 'llama3.1:8b',
    claim_extractor: 'llama3.1:8b',
    contradiction_detector: 'qwen3.5:9b',
    consensus_analyst: 'koesn/llama3-openbiollm-8b:latest',
    synthesis: 'llama3.1:8b',
    experiment_planner: 'llama3.1:8b'
  });
  
  // Pipeline/Log state
  const [ingesting, setIngesting] = useState(false);
  const [pipelineLogs, setPipelineLogs] = useState([]);
  const [pipelineStatus, setPipelineStatus] = useState('');
  
  // Dataset state (loaded from backend status)
  const [hasDataset, setHasDataset] = useState(false);
  const [papers, setPapers] = useState([]);
  const [relations, setRelations] = useState({});
  const [claims, setClaims] = useState([]);
  const [consensusReport, setConsensusReport] = useState('');
  const [protocolDraft, setProtocolDraft] = useState('');
  const [elnEntry, setElnEntry] = useState('');
  const [showNetworkGraph, setShowNetworkGraph] = useState(false);
  const [extractingClaims, setExtractingClaims] = useState(false);
  
  // Active Agent Generation States
  const [generatingSynthesis, setGeneratingSynthesis] = useState(false);
  const [generatingProtocol, setGeneratingProtocol] = useState(false);
  const [generatingEln, setGeneratingEln] = useState(false);
  
  // Critique state
  const [peerReview, setPeerReview] = useState('');
  const [generatingCritique, setGeneratingCritique] = useState(false);
  
  // Report and validation state
  const [overseerReport, setOverseerReport] = useState('');
  const [validationResults, setValidationResults] = useState(null);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [refinementFeedback, setRefinementFeedback] = useState('');
  const [refiningReport, setRefiningReport] = useState(false);
  
  // Chat RAG state
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  
  // Query Planning state
  const [queryPlan, setQueryPlan] = useState(null);
  const [planningQuery, setPlanningQuery] = useState('');
  const [showPlanConfirmation, setShowPlanConfirmation] = useState(false);
  const [buildingPlan, setBuildingPlan] = useState(false);
  const [pipelineExecution, setPipelineExecution] = useState(false);
  const [canStopPipeline, setCanStopPipeline] = useState(false);
  
  // Live Process Monitoring state
  const [activeProcesses, setActiveProcesses] = useState([]);
  const [processHistory, setProcessHistory] = useState([]);
  const [showLiveMonitor, setShowLiveMonitor] = useState(true);
  
  // Refs
  const logsEndRef = useRef(null);
  const chatEndRef = useRef(null);
  const processEndRef = useRef(null);

  // Load dataset status on init
  useEffect(() => {
    fetchStatus();
  }, []);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [pipelineLogs]);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatHistory]);

  useEffect(() => {
    if (processEndRef.current) {
      processEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [activeProcesses, processHistory]);

  // Helper to add process to monitoring
  const addProcess = (process) => {
    const newProcess = {
      ...process,
      id: Date.now() + Math.random(),
      startTime: new Date(),
      status: 'running',
      steps: process.steps || [],
      currentStep: 0,
      logs: []
    };
    setActiveProcesses(prev => [...prev, newProcess]);
    return newProcess.id;
  };

  const updateProcess = (id, updates) => {
    setActiveProcesses(prev => prev.map(p => 
      p.id === id ? { ...p, ...updates } : p
    ));
  };

  const completeProcess = (id, result) => {
    setActiveProcesses(prev => {
      const updated = prev.map(p => 
        p.id === id ? { ...p, status: 'completed', endTime: new Date(), result } : p
      );
      return updated;
    });
    
    // Move to history after delay
    setTimeout(() => {
      setActiveProcesses(prev => {
        const completed = prev.find(p => p.id === id);
        if (completed) {
          setProcessHistory(prev => [completed, ...prev].slice(0, 10));
          return prev.filter(p => p.id !== id);
        }
        return prev;
      });
    }, 3000);
  };

  const failProcess = (id, error) => {
    setActiveProcesses(prev => {
      const updated = prev.map(p => 
        p.id === id ? { ...p, status: 'failed', endTime: new Date(), error } : p
      );
      return updated;
    });
    
    setTimeout(() => {
      setActiveProcesses(prev => {
        const failed = prev.find(p => p.id === id);
        if (failed) {
          setProcessHistory(prev => [failed, ...prev].slice(0, 10));
          return prev.filter(p => p.id !== id);
        }
        return prev;
      });
    }, 5000);
  };

  const addProcessLog = (id, log) => {
    setActiveProcesses(prev => prev.map(p => 
      p.id === id ? { ...p, logs: [...p.logs, { time: new Date(), message: log }] } : p
    ));
  };

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      const data = await res.json();
      setHasDataset(data.has_dataset);
      if (data.has_dataset) {
        setPapers(data.papers || []);
        setRelations(data.relations || {});
        setConsensusReport(data.consensus_report || '');
        setProtocolDraft(data.protocol_draft || '');
        setElnEntry(data.eln_entry || '');
      }
    } catch (err) {
      console.error("Failed to load status:", err);
    }
  };

  // WebSocket Ingestion Pipeline
  const runIngestion = () => {
    if (!query.trim()) return;
    setIngesting(true);
    setPipelineLogs([]);
    setPipelineStatus('Establishing socket connection...');
    
    const processId = addProcess({
      name: 'Data Ingestion Pipeline',
      type: 'ingestion',
      icon: Database,
      steps: ['Connecting to WebSocket', 'Extracting search terms', 'Querying data sources', 'Downloading papers', 'Parsing metadata', 'Generating embeddings', 'Building vector database', 'Indexing complete'],
      query: query.substring(0, 50) + '...'
    });
    
    const ws = new WebSocket(`${WS_BASE}/api/ws/ingest`);
    
    ws.onopen = () => {
      updateProcess(processId, { currentStep: 1, status: 'Connecting to data sources' });
      addProcessLog(processId, 'WebSocket connection established');
      ws.send(JSON.stringify({
        query,
        email,
        sc_key: scKey,
        collector_limits: {
          PubMed: 20,
          PMC: 20,
          OpenAlex: 20,
          ClinicalTrials: 20,
          bioRxiv: 20,
          ChEMBL: 20,
          UniProt: 20
        },
        model_name: selectedModel
      }));
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'status') {
        setPipelineStatus(data.message);
        addProcessLog(processId, data.message);
        // Update step based on status
        if (data.message.includes('PubMed')) updateProcess(processId, { currentStep: 2 });
        else if (data.message.includes('download')) updateProcess(processId, { currentStep: 3 });
        else if (data.message.includes('parsing')) updateProcess(processId, { currentStep: 4 });
        else if (data.message.includes('embedding')) updateProcess(processId, { currentStep: 5 });
        else if (data.message.includes('index')) updateProcess(processId, { currentStep: 6 });
      } else if (data.type === 'log') {
        setPipelineLogs(prev => [...prev, data.message]);
        addProcessLog(processId, data.message);
      } else if (data.type === 'completed') {
        setPipelineStatus('Success!');
        setIngesting(false);
        updateProcess(processId, { currentStep: 7, status: 'Indexing complete' });
        completeProcess(processId, { papersCount: papers.length });
        fetchStatus();
      } else if (data.type === 'error') {
        setPipelineStatus(`Error: ${data.message}`);
        setPipelineLogs(prev => [...prev, `[Pipeline Error] ${data.message}`]);
        setIngesting(false);
        failProcess(processId, data.message);
      }
    };
    
    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      setPipelineStatus(`WebSocket connection failed: ${err.type || 'Unknown error'}`);
      addProcessLog(processId, `WebSocket connection failed: ${err.type || 'Unknown error'}`);
      setIngesting(false);
      failProcess(processId, 'WebSocket connection failed');
    };
    
    ws.onclose = () => {
      setIngesting(false);
    };
  };

  // Run Synthesis Agent
  const generateSynthesis = async () => {
    const processId = addProcess({
      name: 'Scientific Consensus Analysis',
      type: 'analysis',
      icon: BookOpen,
      steps: ['Loading dataset', 'Analyzing paper relationships', 'Computing consensus scores', 'Generating synthesis report'],
      query: query.substring(0, 50) + '...'
    });
    
    setGeneratingSynthesis(true);
    try {
      updateProcess(processId, { currentStep: 1, status: 'Loading dataset' });
      addProcessLog(processId, 'Loading research papers from database');
      
      const res = await fetch(`${API_BASE}/api/synthesis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query, 
          model_name: selectedModel,
          llm_options: {
            temperature: llmTemp,
            num_ctx: llmNumCtx,
            think: llmThink
          }
        })
      });
      
      updateProcess(processId, { currentStep: 2, status: 'Analyzing relationships' });
      addProcessLog(processId, 'Analyzing paper relationships and contradictions');
      
      const data = await res.json();
      
      updateProcess(processId, { currentStep: 3, status: 'Computing consensus' });
      addProcessLog(processId, 'Computing scientific consensus scores');
      
      setConsensusReport(data.consensus_report);
      
      updateProcess(processId, { currentStep: 4, status: 'Complete' });
      completeProcess(processId, { reportLength: data.consensus_report?.length || 0 });
      fetchStatus();
    } catch (err) {
      addProcessLog(processId, `Error: ${err.message}`);
      failProcess(processId, err.message);
      alert(`Synthesis generation failed: ${err.message}`);
    } finally {
      setGeneratingSynthesis(false);
    }
  };

  // Run Protocol Planner & ELN
  const generateProtocol = async () => {
    const protocolId = addProcess({
      name: 'Protocol Design',
      type: 'protocol',
      icon: Beaker,
      steps: ['Analyzing research context', 'Designing experimental protocol', 'Generating protocol document'],
      query: query.substring(0, 50) + '...'
    });
    
    setGeneratingProtocol(true);
    try {
      updateProcess(protocolId, { currentStep: 1, status: 'Analyzing context' });
      addProcessLog(protocolId, 'Analyzing research context and synthesis report');
      
      const res = await fetch(`${API_BASE}/api/protocol`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query, 
          synthesis_report: consensusReport || query, 
          model_name: selectedModel 
        })
      });
      
      updateProcess(protocolId, { currentStep: 2, status: 'Designing protocol' });
      addProcessLog(protocolId, 'Designing experimental protocol');
      
      const data = await res.json();
      setProtocolDraft(data.protocol_draft);
      
      updateProcess(protocolId, { currentStep: 3, status: 'Complete' });
      completeProcess(protocolId, { protocolLength: data.protocol_draft?.length || 0 });
      
      // Auto-run ELN Entry formatting
      const elnId = addProcess({
        name: 'ELN Entry Generation',
        type: 'eln',
        icon: FileText,
        steps: ['Formatting protocol for ELN', 'Generating structured entry'],
        query: 'ELN formatting'
      });
      
      setGeneratingEln(true);
      updateProcess(elnId, { currentStep: 1, status: 'ELN formatting' });
      addProcessLog(elnId, 'Formatting protocol for electronic lab notebook');
      
      const elnRes = await fetch(`${API_BASE}/api/eln`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          researcher_name: 'Dr. Scientist',
          project_name: 'Oncology Research',
          protocol_draft: data.protocol_draft,
          user_notes: 'Automated ELN generation',
          model_name: selectedModel
        })
      });
      
      updateProcess(elnId, { currentStep: 2, status: 'Complete' });
      const elnData = await elnRes.json();
      setElnEntry(elnData.eln_entry);
      completeProcess(elnId, { elnLength: elnData.eln_entry?.length || 0 });
      fetchStatus();
    } catch (err) {
      failProcess(protocolId, err.message);
      alert(`Protocol design failed: ${err.message}`);
    } finally {
      setGeneratingProtocol(false);
      setGeneratingEln(false);
    }
  };

  // Peer Review Critique
  const generateCritique = async () => {
    if (!googleKey) {
      alert("Please enter a Google API Key in the sidebar credentials.");
      return;
    }
    const critiqueId = addProcess({
      name: 'Peer Review Critique',
      type: 'critique',
      icon: Shield,
      steps: ['Analyzing methodology', 'Checking for bias', 'Evaluating sample size', 'Generating critique'],
      query: query.substring(0, 50) + '...'
    });
    
    setGeneratingCritique(true);
    try {
      updateProcess(critiqueId, { currentStep: 1, status: 'Analyzing methodology' });
      addProcessLog(critiqueId, 'Analyzing research methodology and design');
      
      const res = await fetch(`${API_BASE}/api/critique`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          findings: consensusReport,
          model_name: geminiModel,
          api_key: googleKey
        })
      });
      
      updateProcess(critiqueId, { currentStep: 2, status: 'Checking bias' });
      addProcessLog(critiqueId, 'Checking for methodological bias');
      
      const data = await res.json();
      
      updateProcess(critiqueId, { currentStep: 4, status: 'Complete' });
      setPeerReview(data.peer_review);
      completeProcess(critiqueId, { critiqueLength: data.peer_review?.length || 0 });
    } catch (err) {
      addProcessLog(critiqueId, `Error: ${err.message}`);
      failProcess(critiqueId, err.message);
      alert(`Critique generation failed: ${err.message}`);
    } finally {
      setGeneratingCritique(false);
    }
  };

  // Grounded Overseer Report
  const generateReport = async () => {
    if (!googleKey) {
      alert("Please enter a Google API Key in the sidebar credentials.");
      return;
    }
    const reportId = addProcess({
      name: 'Grounded Report Generation',
      type: 'report',
      icon: FileText,
      steps: ['Gathering sources', 'Compiling findings', 'Web validation', 'Quality checks', 'Final report generation'],
      query: query.substring(0, 50) + '...'
    });
    
    setGeneratingReport(true);
    setValidationResults(null);
    try {
      updateProcess(reportId, { currentStep: 1, status: 'Gathering sources' });
      addProcessLog(reportId, 'Gathering research sources and findings');
      
      const res = await fetch(`${API_BASE}/api/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          model_name: geminiModel,
          api_key: googleKey
        })
      });
      
      updateProcess(reportId, { currentStep: 2, status: 'Compiling findings' });
      addProcessLog(reportId, 'Compiling research findings');
      
      const data = await res.json();
      
      updateProcess(reportId, { currentStep: 3, status: 'Web validation' });
      addProcessLog(reportId, 'Running web validation checks');
      
      updateProcess(reportId, { currentStep: 4, status: 'Quality checks' });
      addProcessLog(reportId, 'Performing quality validation');
      
      setOverseerReport(data.report_text);
      setValidationResults(data.validation);
      
      updateProcess(reportId, { currentStep: 5, status: 'Complete' });
      completeProcess(reportId, { reportLength: data.report_text?.length || 0, validationScore: data.validation?.quality_score || 0 });
    } catch (err) {
      addProcessLog(reportId, `Error: ${err.message}`);
      failProcess(reportId, err.message);
      alert(`Report compilation failed: ${err.message}`);
    } finally {
      setGeneratingReport(false);
    }
  };

  // Refine Report
  const refineReport = async () => {
    if (!googleKey || !refinementFeedback.trim()) return;
    setRefiningReport(true);
    try {
      const res = await fetch(`${API_BASE}/api/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_report: overseerReport,
          feedback: refinementFeedback,
          model_name: geminiModel,
          api_key: googleKey
        })
      });
      const data = await res.json();
      setOverseerReport(data.refined_report);
      setRefinementFeedback('');
    } catch (err) {
      alert(`Refinement failed: ${err.message}`);
    } finally {
      setRefiningReport(false);
    }
  };

  // Chat RAG
  const sendChatMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const userMsg = chatInput;
    setChatInput('');
    setChatHistory(prev => [...prev, { role: 'user', content: userMsg }]);
    setChatLoading(true);
    
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userMsg,
          chat_history: chatHistory,
          model_name: selectedModel
        })
      });
      const data = await res.json();
      setChatHistory(prev => [...prev, { 
        role: 'assistant', 
        content: data.answer,
        sources: data.sources 
      }]);
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'assistant', content: `Chat error: ${err.message}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  // Export report
  const downloadReport = () => {
    const blob = new Blob([overseerReport], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'grounded_overseer_report.md';
    a.click();
  };

  // Build Query Plan
  const buildQueryPlan = async () => {
    if (!planningQuery.trim()) return;
    setBuildingPlan(true);
    try {
      const res = await fetch(`${API_BASE}/api/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: planningQuery,
          model_name: selectedModel 
        })
      });
      const data = await res.json();
      // Map backend response to frontend format
      setQueryPlan({
        intent: data.explanation || 'Research query',
        route: data.routing?.planner || 'Standard RAG Pipeline',
        model: data.routing?.planner || selectedModel,
        search_terms: data.target_collectors || [],
        pipeline_steps: data.required_agents || ['Ingestion', 'Analysis', 'Synthesis']
      });
      setShowPlanConfirmation(true);
    } catch (err) {
      alert(`Failed to build query plan: ${err.message}`);
    } finally {
      setBuildingPlan(false);
    }
  };

  // Execute Query Plan
  const executeQueryPlan = async () => {
    if (!queryPlan) return;
    setShowPlanConfirmation(false);
    setPipelineExecution(true);
    setCanStopPipeline(true);
    
    const processId = addProcess({
      name: 'Query Plan Execution',
      type: 'pipeline',
      icon: Compass,
      steps: ['Initializing pipeline', 'Retrieving papers', 'Extracting claims', 'Detecting contradictions', 'Analyzing consensus', 'Generating synthesis', 'Complete'],
      query: planningQuery.substring(0, 50) + '...'
    });

    // Use the existing WebSocket ingestion endpoint
    const ws = new WebSocket(`${WS_BASE}/api/ws/ingest`);
    
    ws.onopen = () => {
      updateProcess(processId, { currentStep: 1, status: 'Connecting to data sources' });
      addProcessLog(processId, 'WebSocket connection established');
      ws.send(JSON.stringify({
        query: planningQuery,
        email,
        sc_key: scKey,
        collector_limits: {
          PubMed: 20,
          PMC: 20,
          OpenAlex: 20,
          ClinicalTrials: 20,
          bioRxiv: 20,
          ChEMBL: 20,
          UniProt: 20
        },
        model_name: selectedModel
      }));
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'status') {
        addProcessLog(processId, data.message);
        // Update step based on status
        if (data.message.includes('PubMed')) updateProcess(processId, { currentStep: 2 });
        else if (data.message.includes('download')) updateProcess(processId, { currentStep: 3 });
        else if (data.message.includes('parsing')) updateProcess(processId, { currentStep: 4 });
        else if (data.message.includes('embedding')) updateProcess(processId, { currentStep: 5 });
        else if (data.message.includes('index')) updateProcess(processId, { currentStep: 6 });
      } else if (data.type === 'log') {
        addProcessLog(processId, data.message);
      } else if (data.type === 'completed') {
        updateProcess(processId, { currentStep: 6, status: 'Complete' });
        completeProcess(processId, { papersCount: data.papers?.length || 0 });
        setHasDataset(true);
        fetchStatus();
      } else if (data.type === 'error') {
        addProcessLog(processId, `[Pipeline Error] ${data.message}`);
        failProcess(processId, data.message);
      }
    };
    
    ws.onerror = (err) => {
      addProcessLog(processId, 'WebSocket connection failed');
      failProcess(processId, 'WebSocket connection failed');
    };
    
    ws.onclose = () => {
      setPipelineExecution(false);
      setCanStopPipeline(false);
    };
  };

  // Stop Pipeline Execution
  const stopPipeline = () => {
    setPipelineExecution(false);
    setCanStopPipeline(false);
    // In a real implementation, this would send a cancel signal to the backend
  };

  // Methodology Audit
  const auditMethodology = (paper) => {
    const flags = [];
    
    // Check sample size
    if (paper.sample_size === null || paper.sample_size === -1) {
      flags.push({ type: 'warning', message: 'Sample size not reported' });
    } else if (paper.sample_size < 50) {
      flags.push({ type: 'error', message: 'Small sample size (<50)' });
    } else if (paper.sample_size < 100) {
      flags.push({ type: 'warning', message: 'Moderate sample size (<100)' });
    }
    
    // Check study design
    const design = paper.study_design?.toLowerCase() || '';
    if (design.includes('retrospective')) {
      flags.push({ type: 'warning', message: 'Retrospective design' });
    }
    if (design.includes('open-label')) {
      flags.push({ type: 'warning', message: 'Open-label bias risk' });
    }
    if (!design || design === 'undetermined') {
      flags.push({ type: 'error', message: 'Study design not specified' });
    }
    
    // Check evidence score
    if (paper.evidence_score < 5) {
      flags.push({ type: 'error', message: 'Low evidence score' });
    } else if (paper.evidence_score < 7) {
      flags.push({ type: 'warning', message: 'Moderate evidence score' });
    }
    
    return flags;
  };

  // Extract Claims - Disabled as endpoint not available in backend
  const extractClaims = async () => {
    alert('Claim extraction endpoint not yet implemented in backend. Please use the Streamlit app for claim extraction.');
  };

  return (
    <div className="app-container">
      {/* Live Process Monitor */}
      {showLiveMonitor && (
        <div style={{
          position: 'fixed',
          top: '20px',
          right: '20px',
          width: '380px',
          maxHeight: '70vh',
          zIndex: 1000,
          background: 'rgba(9, 11, 22, 0.95)',
          backdropFilter: 'blur(20px)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}>
          {/* Monitor Header */}
          <div style={{
            padding: '16px',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'linear-gradient(135deg, rgba(99,102,241,0.1), rgba(168,85,247,0.1))'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ background: 'linear-gradient(135deg, var(--accent-indigo), var(--accent-purple))', padding: '8px', borderRadius: '8px' }}>
                <Activity size={16} color="white" />
              </div>
              <div>
                <div style={{ fontSize: '14px', fontWeight: '600', color: 'white' }}>Live Process Monitor</div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Real-time agent activity</div>
              </div>
            </div>
            <button 
              onClick={() => setShowLiveMonitor(false)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                padding: '4px'
              }}
            >
              ✕
            </button>
          </div>

          {/* Active Processes */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '12px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {activeProcesses.length === 0 && processHistory.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: '40px 20px',
                color: 'var(--text-muted)',
                fontSize: '12px'
              }}>
                <Activity size={32} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
                <div>No active processes</div>
                <div style={{ fontSize: '11px', marginTop: '4px' }}>Start an agent to see live progress</div>
              </div>
            ) : (
              <>
                {/* Active Processes */}
                {activeProcesses.map(process => {
                  const Icon = process.icon || Activity;
                  const progress = ((process.currentStep + 1) / process.steps.length) * 100;
                  const elapsed = Math.floor((new Date() - process.startTime) / 1000);
                  
                  return (
                    <div key={process.id} style={{
                      background: 'rgba(0,0,0,0.3)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      padding: '12px',
                      position: 'relative',
                      overflow: 'hidden'
                    }}>
                      {/* Animated border gradient */}
                      <div style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: '2px',
                        background: 'linear-gradient(90deg, var(--accent-indigo), var(--accent-purple), var(--accent-indigo))',
                        backgroundSize: '200% 100%',
                        animation: 'gradientMove 2s linear infinite'
                      }} />
                      
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                        <div style={{
                          background: 'linear-gradient(135deg, var(--accent-indigo), var(--accent-purple))',
                          padding: '6px',
                          borderRadius: '6px'
                        }}>
                          <Icon size={14} color="white" />
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: '13px', fontWeight: '600', color: 'white' }}>{process.name}</div>
                          <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{process.query}</div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: 'var(--accent-indigo)' }}>
                          <Clock size={12} />
                          {elapsed}s
                        </div>
                      </div>

                      {/* Progress Bar */}
                      <div style={{ marginBottom: '10px' }}>
                        <div style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          fontSize: '11px',
                          color: 'var(--text-secondary)',
                          marginBottom: '4px'
                        }}>
                          <span>{process.steps[process.currentStep] || process.status}</span>
                          <span>{Math.round(progress)}%</span>
                        </div>
                        <div style={{
                          height: '4px',
                          background: 'rgba(255,255,255,0.1)',
                          borderRadius: '2px',
                          overflow: 'hidden'
                        }}>
                          <div style={{
                            height: '100%',
                            width: `${progress}%`,
                            background: 'linear-gradient(90deg, var(--accent-indigo), var(--accent-purple))',
                            borderRadius: '2px',
                            transition: 'width 0.3s ease'
                          }} />
                        </div>
                      </div>

                      {/* Steps Timeline */}
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                        {process.steps.map((step, idx) => (
                          <div key={idx} style={{
                            fontSize: '10px',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: idx < process.currentStep 
                              ? 'rgba(16,185,129,0.2)' 
                              : idx === process.currentStep 
                              ? 'rgba(99,102,241,0.2)' 
                              : 'rgba(255,255,255,0.05)',
                            color: idx < process.currentStep 
                              ? 'var(--accent-emerald)' 
                              : idx === process.currentStep 
                              ? 'var(--accent-indigo)' 
                              : 'var(--text-muted)',
                            border: idx === process.currentStep 
                              ? '1px solid var(--accent-indigo)' 
                              : 'none'
                          }}>
                            {idx + 1}
                          </div>
                        ))}
                      </div>

                      {/* Recent Logs */}
                      {process.logs.length > 0 && (
                        <div style={{
                          marginTop: '10px',
                          padding: '8px',
                          background: 'rgba(0,0,0,0.2)',
                          borderRadius: '4px',
                          fontSize: '10px',
                          fontFamily: 'var(--font-mono)',
                          color: '#A5B4FC',
                          maxHeight: '60px',
                          overflowY: 'auto'
                        }}>
                          {process.logs.slice(-3).map((log, idx) => (
                            <div key={idx} style={{ marginBottom: '2px' }}>
                              <span style={{ color: 'var(--text-muted)' }}>[{log.time.toLocaleTimeString()}]</span> {log.message}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Process History */}
                {processHistory.length > 0 && (
                  <div style={{ marginTop: '8px' }}>
                    <div style={{
                      fontSize: '11px',
                      fontWeight: '600',
                      color: 'var(--text-secondary)',
                      marginBottom: '8px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px'
                    }}>
                      Recent Activity
                    </div>
                    {processHistory.map(process => {
                      const Icon = process.icon || Activity;
                      const duration = process.endTime 
                        ? Math.floor((process.endTime - process.startTime) / 1000) 
                        : 0;
                      
                      return (
                        <div key={process.id} style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          padding: '8px',
                          background: process.status === 'completed' 
                            ? 'rgba(16,185,129,0.05)' 
                            : 'rgba(244,63,94,0.05)',
                          borderRadius: '6px',
                          border: process.status === 'completed'
                            ? '1px solid rgba(16,185,129,0.1)'
                            : '1px solid rgba(244,63,94,0.1)',
                          marginBottom: '6px'
                        }}>
                          <Icon size={12} color={process.status === 'completed' ? 'var(--accent-emerald)' : 'var(--accent-rose)'} />
                          <div style={{ flex: 1, fontSize: '11px', color: 'var(--text-secondary)' }}>
                            {process.name}
                          </div>
                          <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                            {duration}s
                          </div>
                          {process.status === 'completed' ? (
                            <CheckCircle size={12} color="var(--accent-emerald)" />
                          ) : (
                            <AlertTriangle size={12} color="var(--accent-rose)" />
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
            <div ref={processEndRef} />
          </div>
        </div>
      )}

      {/* Floating toggle button when monitor is hidden */}
      {!showLiveMonitor && (
        <button
          onClick={() => setShowLiveMonitor(true)}
          style={{
            position: 'fixed',
            top: '20px',
            right: '20px',
            zIndex: 1000,
            background: 'linear-gradient(135deg, var(--accent-indigo), var(--accent-purple))',
            border: 'none',
            borderRadius: '50%',
            width: '48px',
            height: '48px',
            cursor: 'pointer',
            boxShadow: '0 4px 16px rgba(99,102,241,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <Activity size={20} color="white" />
        </button>
      )}

      {/* Sidebar controls */}
      <div className="sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', paddingBottom: '10px', borderBottom: '1px solid var(--border-color)' }}>
          <div style={{ background: 'linear-gradient(135deg, var(--accent-indigo), var(--accent-purple))', padding: '6px', borderRadius: '8px' }}>
            <Compass size={20} color="white" />
          </div>
          <h2 style={{ fontSize: '18px', fontWeight: '600', letterSpacing: '-0.5px' }}>Griffin Bio Studio</h2>
        </div>

        {/* Credentials Form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
            <Settings size={14} />
            <span style={{ fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Credentials & Models</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>PubMed Email</label>
            <input type="text" value={email} onChange={e => setEmail(e.target.value)} placeholder="Email..." />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Semantic Scholar API Key</label>
            <input type="password" value={scKey} onChange={e => setScKey(e.target.value)} placeholder="Optional..." />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Google API Key (Gemini)</label>
            <input type="password" value={googleKey} onChange={e => setGoogleKey(e.target.value)} placeholder="Required for Report/Validation..." />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Local Ollama Model</label>
            <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}>
              <option value="gemma3:4b">gemma3:4b</option>
              <option value="gemma3:latest">gemma3:latest</option>
              <option value="koesn/llama3-openbiollm-8b:latest">OpenBioLLM-8b</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Gemini Report Model</label>
            <select value={geminiModel} onChange={e => setGeminiModel(e.target.value)}>
              <option value="gemini-2.5-flash">gemini-2.5-flash</option>
              <option value="gemini-2.5-pro">gemini-2.5-pro</option>
              <option value="gemini-1.5-flash">gemini-1.5-flash</option>
            </select>
          </div>

          {/* LLM Tuning Controls */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '8px', borderTop: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
              <Settings size={14} />
              <span style={{ fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>LLM Options</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                Temperature: {llmTemp}
              </label>
              <input 
                type="range" 
                min="0" 
                max="2" 
                step="0.1" 
                value={llmTemp} 
                onChange={(e) => setLlmTemp(parseFloat(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Context Length</label>
              <select value={llmNumCtx} onChange={(e) => setLlmNumCtx(parseInt(e.target.value))}>
                <option value={2048}>2048 tokens</option>
                <option value={4096}>4096 tokens</option>
                <option value={8192}>8192 tokens</option>
                <option value={16384}>16384 tokens</option>
                <option value={32768}>32768 tokens</option>
                <option value={65536}>65536 tokens</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <input 
                type="checkbox" 
                checked={llmThink} 
                onChange={(e) => setLlmThink(e.target.checked)}
                id="think-mode"
              />
              <label htmlFor="think-mode" style={{ fontSize: '11px', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Enable Thinking Mode
              </label>
            </div>
          </div>

          {/* Model Routing Controls */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '8px', borderTop: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
              <Network size={14} />
              <span style={{ fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Model Routing</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <input 
                type="checkbox" 
                checked={useGlobalModel} 
                onChange={(e) => setUseGlobalModel(e.target.checked)}
                id="global-model"
              />
              <label htmlFor="global-model" style={{ fontSize: '11px', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Use Global Model
              </label>
            </div>

            {!useGlobalModel && (
              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                Per-agent routing (advanced)
              </div>
            )}
          </div>
        </div>

        {/* Sidebar RAG Chat */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: '280px', borderTop: '1px solid var(--border-color)', paddingTop: '15px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
            <MessageSquare size={14} />
            <span style={{ fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Ask the Dataset</span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', padding: '10px', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '8px', maxHeight: '300px' }}>
            {chatHistory.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '12px', textAlign: 'center', marginTop: '20px' }}>
                Ask questions about your loaded research papers.
              </div>
            ) : (
              chatHistory.map((m, idx) => (
                <div key={idx} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%', background: m.role === 'user' ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.05)', padding: '8px 12px', borderRadius: '8px', fontSize: '12px', border: '1px solid var(--border-color)' }}>
                  <strong>{m.role === 'user' ? 'You' : 'AI'}:</strong> {m.content}
                  {m.sources && (
                    <div style={{ fontSize: '10px', color: 'var(--accent-indigo)', marginTop: '4px', textDecoration: 'underline', cursor: 'pointer' }}>
                      Cited: {m.sources.map(s => `[${s.index}]`).join(', ')}
                    </div>
                  )}
                </div>
              ))
            )}
            <div ref={chatEndRef} />
          </div>

          <div style={{ display: 'flex', gap: '4px' }}>
            <input type="text" value={chatInput} onChange={e => setChatInput(e.target.value)} placeholder="Type a question..." style={{ flex: 1 }} onKeyDown={e => e.key === 'Enter' && sendChatMessage()} />
            <button className="btn btn-secondary" style={{ padding: '8px' }} onClick={sendChatMessage} disabled={chatLoading}>
              {chatLoading ? <Loader size={14} className="animate-spin" /> : <Send size={14} />}
            </button>
          </div>
        </div>
      </div>

      {/* Main workspaces */}
      <div className="main-content">
        <div className="tabs-header">
          {[
            { label: '🧭 Query Planner', icon: Compass },
            { label: '📝 Scientific Consensus', icon: BookOpen },
            { label: '⚡ Contradictions & Agreements', icon: Zap },
            { label: '📚 Ranked Clinical Evidence', icon: FileText },
            { label: '🔎 Claims Exploration', icon: Search },
            { label: '📋 Grounded Report', icon: Shield }
          ].map((tab, idx) => {
            const Icon = tab.icon;
            return (
              <button key={idx} className={`tab-btn ${activeTab === idx ? 'active' : ''}`} onClick={() => setActiveTab(idx)}>
                <Icon size={14} style={{ marginRight: '6px', display: 'inline-block', verticalAlign: 'middle' }} />
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="tab-panel">
          {/* Tab 0: Query Planner & log timeline */}
          {activeTab === 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div className="glass" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '8px' }}>🧭 Query Planner & Intent Detection</h3>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>Enter a research query. The system will analyze your intent, build an execution plan, and show you the route before execution.</p>
                
                <div style={{ display: 'flex', gap: '10px' }}>
                  <textarea 
                    value={planningQuery} 
                    onChange={e => setPlanningQuery(e.target.value)} 
                    placeholder="Enter research query (e.g., 'Does Metformin combine synergistically with other drugs for breast cancer?')" 
                    style={{ flex: 1, height: '60px' }} 
                  />
                  <button className="btn btn-primary" onClick={buildQueryPlan} disabled={buildingPlan || !planningQuery.trim()} style={{ height: '60px' }}>
                    {buildingPlan ? <Loader className="animate-spin" size={16} /> : <Compass size={16} />}
                    {buildingPlan ? 'Analyzing...' : 'Build Plan'}
                  </button>
                </div>
              </div>

              {/* Query Plan Confirmation Dialog */}
              {showPlanConfirmation && queryPlan && (
                <div className="glass" style={{ padding: '24px', border: '2px solid var(--accent-indigo)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                    <div style={{ background: 'linear-gradient(135deg, var(--accent-indigo), var(--accent-purple))', padding: '8px', borderRadius: '8px' }}>
                      <Info size={20} color="white" />
                    </div>
                    <div>
                      <h3 style={{ fontSize: '16px', fontWeight: '600', margin: 0 }}>Query Plan Ready for Execution</h3>
                      <p style={{ color: 'var(--text-secondary)', fontSize: '12px', margin: 0 }}>Review the parsed intent and route before proceeding</p>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px', marginBottom: '20px' }}>
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px' }}>Research Intent</div>
                      <div style={{ fontSize: '14px', color: 'white', fontWeight: '500' }}>{queryPlan.intent || 'General research query'}</div>
                    </div>
                    
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px' }}>Assigned Route</div>
                      <div style={{ fontSize: '14px', color: 'var(--accent-indigo)', fontWeight: '500' }}>{queryPlan.route || 'Standard RAG Pipeline'}</div>
                    </div>
                    
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px' }}>Primary Model</div>
                      <div style={{ fontSize: '14px', color: 'var(--accent-purple)', fontWeight: '500' }}>{queryPlan.model || selectedModel}</div>
                    </div>
                  </div>

                  {queryPlan.search_terms && queryPlan.search_terms.length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px' }}>Extracted Search Terms</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {queryPlan.search_terms.map((term, idx) => (
                          <span key={idx} className="badge badge-indigo" style={{ fontSize: '12px' }}>{term}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {queryPlan.pipeline_steps && queryPlan.pipeline_steps.length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px' }}>Pipeline Steps</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {queryPlan.pipeline_steps.map((step, idx) => (
                          <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                            <div style={{ 
                              width: '24px', 
                              height: '24px', 
                              borderRadius: '50%', 
                              background: 'rgba(99,102,241,0.2)', 
                              border: '1px solid var(--accent-indigo)', 
                              display: 'flex', 
                              alignItems: 'center', 
                              justifyContent: 'center',
                              fontSize: '11px',
                              color: 'var(--accent-indigo)',
                              fontWeight: '600'
                            }}>
                              {idx + 1}
                            </div>
                            {step}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                    <button className="btn btn-secondary" onClick={() => setShowPlanConfirmation(false)}>
                      Modify Plan
                    </button>
                    <button className="btn btn-primary" onClick={executeQueryPlan}>
                      <Play size={16} style={{ marginRight: '8px' }} />
                      Execute Pipeline
                    </button>
                  </div>
                </div>
              )}

              {/* Pipeline Execution with Stop Button */}
              {pipelineExecution && (
                <div className="glass" style={{ padding: '20px', border: '2px solid var(--accent-emerald)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <Loader size={20} className="animate-spin" color="var(--accent-emerald)" />
                      <div>
                        <h4 style={{ fontSize: '14px', fontWeight: '600', margin: 0 }}>Pipeline Executing</h4>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '12px', margin: 0 }}>Running query plan through analysis stages</p>
                      </div>
                    </div>
                    {canStopPipeline && (
                      <button 
                        className="btn btn-secondary" 
                        onClick={stopPipeline}
                        style={{ background: 'rgba(244,63,94,0.2)', border: '1px solid rgba(244,63,94,0.3)', color: 'var(--accent-rose)' }}
                      >
                        <AlertTriangle size={14} style={{ marginRight: '6px' }} />
                        Stop Pipeline
                      </button>
                    )}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Monitor progress in the Live Process Monitor (top-right)
                  </div>
                </div>
              )}

              {/* Legacy ingestion section */}
              <div className="glass" style={{ padding: '20px', opacity: 0.7 }}>
                <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px', color: 'var(--text-secondary)' }}>Legacy Direct Ingestion</h4>
                <p style={{ color: 'var(--text-muted)', fontSize: '12px', marginBottom: '12px' }}>Direct pipeline execution without query planning (deprecated)</p>
                
                <div style={{ display: 'flex', gap: '10px' }}>
                  <textarea 
                    value={query} 
                    onChange={e => setQuery(e.target.value)} 
                    placeholder="Enter query for direct ingestion..." 
                    style={{ flex: 1, height: '40px', fontSize: '12px' }} 
                  />
                  <button className="btn btn-secondary" onClick={runIngestion} disabled={ingesting || !query.trim()} style={{ height: '40px', fontSize: '12px' }}>
                    {ingesting ? <Loader className="animate-spin" size={14} /> : <Play size={14} />}
                    Run Direct
                  </button>
                </div>
              </div>

              {/* Log trace display */}
              {(pipelineLogs.length > 0 || ingesting) && (
                <div className="glass" style={{ padding: '20px', background: '#090B16' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <h4 style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Pipeline Execution Logs</h4>
                    <span className="badge badge-indigo">{pipelineStatus}</span>
                  </div>
                  <div style={{ background: 'rgba(0,0,0,0.4)', borderRadius: '8px', padding: '15px', height: '250px', overflowY: 'auto', fontFamily: 'var(--font-mono)', fontSize: '12px', color: '#A5B4FC', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {pipelineLogs.map((log, idx) => (
                      <div key={idx} style={{ display: 'flex', gap: '10px' }}>
                        <span style={{ color: 'var(--text-muted)' }}>[{idx+1}]</span>
                        <span>{log}</span>
                      </div>
                    ))}
                    {ingesting && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-indigo)' }}>
                        <Loader size={12} className="animate-spin" />
                        <span>Processing next step...</span>
                      </div>
                    )}
                    <div ref={logsEndRef} />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab 1: Scientific Consensus */}
          {activeTab === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div className="glass" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: '600' }}>🔬 Scientific Consensus Analyst</h3>
                    <p style={{ color: 'var(--text-secondary)' }}>Synthesize multi-paper evidence to compute consistency ratings and explore scientific alignment.</p>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button className="btn btn-primary" onClick={generateSynthesis} disabled={generatingSynthesis || !hasDataset}>
                      {generatingSynthesis ? <Loader className="animate-spin" size={14} /> : <BookOpen size={14} />}
                      {generatingSynthesis ? 'Analyzing...' : 'Generate Consensus Report'}
                    </button>
                    {consensusReport && (
                      <button className="btn btn-secondary" onClick={() => {
                        const blob = new Blob([consensusReport], { type: 'text/markdown' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'consensus_report.md';
                        a.click();
                      }}>
                        <Download size={14} />
                      </button>
                    )}
                  </div>
                </div>

                {consensusReport ? (
                  <div>
                    <div style={{ marginBottom: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span className="badge badge-emerald">✓ Report Generated</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{consensusReport.length} characters</span>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '20px', borderRadius: '8px', border: '1px solid var(--border-color)', whiteSpace: 'pre-wrap', fontSize: '13px', lineHeight: '1.6', maxHeight: '400px', overflowY: 'auto' }}>
                      {consensusReport}
                    </div>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    <BookOpen size={32} style={{ marginBottom: '12px', opacity: 0.5 }} />
                    <div>No consensus report generated</div>
                    <div style={{ fontSize: '12px', marginTop: '4px' }}>Click the button above to run the analysis</div>
                  </div>
                )}
              </div>

              {/* Peer review section */}
              {consensusReport && (
                <div className="glass" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                    <div>
                      <h4 style={{ fontSize: '14px', fontWeight: '600' }}>⚖️ Devil's Advocate / Peer Review Critique</h4>
                      <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Audit findings for methodological bias, sample size bounds, and study limits.</p>
                    </div>
                    <button className="btn btn-secondary" onClick={generateCritique} disabled={generatingCritique}>
                      {generatingCritique ? <Loader className="animate-spin" size={14} /> : <Shield size={14} />}
                      {generatingCritique ? 'Reviewing...' : 'Generate Peer Critique'}
                    </button>
                  </div>

                  {peerReview ? (
                    <div style={{ background: 'rgba(244,63,94,0.03)', padding: '15px', borderRadius: '8px', border: '1px solid rgba(244,63,94,0.15)', whiteSpace: 'pre-wrap', fontSize: '13px', color: '#FDA4AF' }}>
                      {peerReview}
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)', fontSize: '12px' }}>
                      No peer critique generated yet
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Contradictions & agreements */}
          {activeTab === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div className="glass" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '4px' }}>⚡ Contradictions & Scientific Disputes</h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Extract claims, detect contradictions, and visualize claim relationships</p>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button 
                      className="btn btn-secondary" 
                      onClick={extractClaims} 
                      disabled={extractingClaims || !hasDataset}
                    >
                      {extractingClaims ? <Loader className="animate-spin" size={14} /> : <Search size={14} />}
                      {extractingClaims ? 'Extracting...' : 'Extract Claims'}
                    </button>
                    {claims.length > 0 && (
                      <button 
                        className="btn btn-secondary" 
                        onClick={() => setShowNetworkGraph(!showNetworkGraph)}
                      >
                        <Network size={14} style={{ marginRight: '6px' }} />
                        {showNetworkGraph ? 'Hide Graph' : 'Show Graph'}
                      </button>
                    )}
                  </div>
                </div>

                {/* Network Graph Visualization */}
                {showNetworkGraph && claims.length > 0 && (
                  <div style={{ 
                    marginBottom: '20px', 
                    background: 'rgba(0,0,0,0.3)', 
                    borderRadius: '8px', 
                    padding: '20px',
                    border: '1px solid var(--border-color)'
                  }}>
                    <div style={{ marginBottom: '12px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      <strong>Claim Relationship Network</strong> - Visualizing contradictions, agreements, and partial agreements
                    </div>
                    <div style={{ 
                      height: '300px', 
                      background: 'rgba(0,0,0,0.2)', 
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--text-muted)',
                      fontSize: '13px'
                    }}>
                      <div style={{ textAlign: 'center' }}>
                        <Network size={48} style={{ marginBottom: '12px', opacity: 0.5 }} />
                        <div>Interactive network graph visualization</div>
                        <div style={{ fontSize: '11px', marginTop: '4px' }}>
                          {relations.contradictions?.length || 0} contradictions, 
                          {relations.agreements?.length || 0} agreements,
                          {relations.partial_agreements?.length || 0} partial agreements
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Claims List */}
                {claims.length > 0 && (
                  <div style={{ marginBottom: '20px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', fontWeight: '600' }}>
                      Extracted Claims ({claims.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '200px', overflowY: 'auto' }}>
                      {claims.map((claim, idx) => (
                        <div key={idx} style={{ 
                          background: 'rgba(0,0,0,0.2)', 
                          padding: '10px 12px', 
                          borderRadius: '6px',
                          border: '1px solid var(--border-color)',
                          fontSize: '12px'
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: '500' }}>{claim.text || claim.claim_text || 'Untitled claim'}</span>
                            <span className={`badge ${claim.stance === 'supports' ? 'badge-emerald' : claim.stance === 'contradicts' ? 'badge-rose' : 'badge-indigo'}`} style={{ fontSize: '10px' }}>
                              {claim.stance || 'neutral'}
                            </span>
                          </div>
                          {claim.paper_title && (
                            <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
                              Source: {claim.paper_title}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Contradictions */}
                <div style={{ marginBottom: '20px' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', fontWeight: '600' }}>
                    Contradictions ({relations.contradictions?.length || 0})
                  </div>
                  {relations.contradictions && relations.contradictions.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {relations.contradictions.map((c, idx) => (
                        <div key={idx} style={{ background: 'rgba(244,63,94,0.03)', border: '1px solid rgba(244,63,94,0.15)', padding: '15px', borderRadius: '8px' }}>
                          <span className="badge badge-rose" style={{ marginBottom: '8px' }}>Contradiction</span>
                          <div style={{ fontWeight: '600', marginBottom: '4px', fontSize: '13px' }}>Claim A: {c.claim_a_title}</div>
                          <div style={{ fontWeight: '600', marginBottom: '8px', fontSize: '13px' }}>Claim B: {c.claim_b_title}</div>
                          <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}><strong>Explanation:</strong> {c.explanation}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ padding: '20px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                      No contradictions detected
                    </div>
                  )}
                </div>

                {/* Agreements */}
                <div style={{ marginBottom: '20px' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', fontWeight: '600' }}>
                    Agreements ({relations.agreements?.length || 0})
                  </div>
                  {relations.agreements && relations.agreements.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {relations.agreements.map((a, idx) => (
                        <div key={idx} style={{ background: 'rgba(16,185,129,0.03)', border: '1px solid rgba(16,185,129,0.15)', padding: '15px', borderRadius: '8px' }}>
                          <span className="badge badge-emerald" style={{ marginBottom: '8px' }}>Agreement</span>
                          <div style={{ fontWeight: '600', marginBottom: '4px', fontSize: '13px' }}>Claim A: {a.claim_a_title}</div>
                          <div style={{ fontWeight: '600', marginBottom: '8px', fontSize: '13px' }}>Claim B: {a.claim_b_title}</div>
                          <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}><strong>Explanation:</strong> {a.explanation}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ padding: '20px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                      No agreements detected
                    </div>
                  )}
                </div>

                {/* Partial Agreements */}
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', fontWeight: '600' }}>
                    Partial Agreements ({relations.partial_agreements?.length || 0})
                  </div>
                  {relations.partial_agreements && relations.partial_agreements.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {relations.partial_agreements.map((p, idx) => (
                        <div key={idx} style={{ background: 'rgba(251,191,36,0.03)', border: '1px solid rgba(251,191,36,0.15)', padding: '15px', borderRadius: '8px' }}>
                          <span className="badge" style={{ marginBottom: '8px', background: 'rgba(251,191,36,0.2)', border: '1px solid rgba(251,191,36,0.3)', color: 'var(--accent-amber)' }}>Partial Agreement</span>
                          <div style={{ fontWeight: '600', marginBottom: '4px', fontSize: '13px' }}>Claim A: {p.claim_a_title}</div>
                          <div style={{ fontWeight: '600', marginBottom: '8px', fontSize: '13px' }}>Claim B: {p.claim_b_title}</div>
                          <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}><strong>Explanation:</strong> {p.explanation}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ padding: '20px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                      No partial agreements detected
                    </div>
                  )}
                </div>

                {claims.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    <Search size={32} style={{ marginBottom: '12px', opacity: 0.5 }} />
                    <div>No claims extracted yet</div>
                    <div style={{ fontSize: '12px', marginTop: '4px' }}>Click "Extract Claims" to analyze the dataset</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab 3: Ranked Evidence */}
          {activeTab === 3 && (
            <div className="glass" style={{ padding: '20px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '15px' }}>📚 Ranked Clinical Evidence</h3>
              {papers.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
                        <th style={{ padding: '12px 8px' }}>Title</th>
                        <th style={{ padding: '12px 8px' }}>Study Design</th>
                        <th style={{ padding: '12px 8px' }}>Sample Size</th>
                        <th style={{ padding: '12px 8px' }}>Score</th>
                        <th style={{ padding: '12px 8px' }}>Methodology Audit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {papers.map((p, idx) => {
                        const auditFlags = auditMethodology(p);
                        return (
                          <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                            <td style={{ padding: '12px 8px', maxWidth: '350px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.title}</td>
                            <td style={{ padding: '12px 8px' }}>
                              <span className={`badge ${p.study_design?.includes('Review') ? 'badge-indigo' : 'badge-emerald'}`}>
                                {p.study_design || 'Undetermined'}
                              </span>
                            </td>
                            <td style={{ padding: '12px 8px' }}>{p.sample_size === -1 || p.sample_size === null ? 'N/A' : p.sample_size}</td>
                            <td style={{ padding: '12px 8px', fontWeight: '600', color: 'var(--accent-indigo)' }}>{p.evidence_score}/10</td>
                            <td style={{ padding: '12px 8px' }}>
                              {auditFlags.length > 0 ? (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                  {auditFlags.map((flag, flagIdx) => (
                                    <span 
                                      key={flagIdx} 
                                      className="badge"
                                      style={{ 
                                        fontSize: '10px',
                                        background: flag.type === 'error' ? 'rgba(244,63,94,0.2)' : 'rgba(251,191,36,0.2)',
                                        border: flag.type === 'error' ? '1px solid rgba(244,63,94,0.3)' : '1px solid rgba(251,191,36,0.3)',
                                        color: flag.type === 'error' ? 'var(--accent-rose)' : 'var(--accent-amber)'
                                      }}
                                    >
                                      {flag.type === 'error' ? '⚠️' : '⚡'} {flag.message}
                                    </span>
                                  ))}
                                </div>
                              ) : (
                                <span className="badge badge-emerald" style={{ fontSize: '10px' }}>✓ No issues</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No papers loaded in active dataset.
                </div>
              )}
            </div>
          )}

          {/* Tab 4: Claims Exploration */}
          {activeTab === 4 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div className="glass" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '4px' }}>🔎 Claims & Stances Table</h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Explore individual arguments and stances mapped to paper extracts</p>
                  </div>
                </div>
                
                {claims.length > 0 ? (
                  <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)', position: 'sticky', top: 0, background: '#090B16' }}>
                          <th style={{ padding: '12px 8px' }}>Claim</th>
                          <th style={{ padding: '12px 8px' }}>Stance</th>
                          <th style={{ padding: '12px 8px' }}>Source Paper</th>
                          <th style={{ padding: '12px 8px' }}>Evidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {claims.map((claim, idx) => (
                          <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                            <td style={{ padding: '12px 8px', maxWidth: '400px', fontSize: '13px' }}>{claim.text || claim.claim_text || 'N/A'}</td>
                            <td style={{ padding: '12px 8px' }}>
                              <span className={`badge ${claim.stance === 'supports' ? 'badge-emerald' : claim.stance === 'contradicts' ? 'badge-rose' : 'badge-indigo'}`} style={{ fontSize: '11px' }}>
                                {claim.stance || 'neutral'}
                              </span>
                            </td>
                            <td style={{ padding: '12px 8px', maxWidth: '250px', fontSize: '12px', color: 'var(--text-secondary)' }}>{claim.paper_title || 'N/A'}</td>
                            <td style={{ padding: '12px 8px', fontSize: '12px' }}>{claim.evidence_score !== undefined ? claim.evidence_score + '/10' : 'N/A'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    <Search size={32} style={{ marginBottom: '12px', opacity: 0.5 }} />
                    <div>No claims extracted yet</div>
                    <div style={{ fontSize: '12px', marginTop: '4px' }}>Extract claims from the Contradictions tab first</div>
                  </div>
                )}
              </div>

              {/* Protocol & ELN Generation Section */}
              <div className="glass" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '4px' }}>🧪 Protocol Design & ELN Entry</h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Generate experimental protocols and electronic lab notebook entries</p>
                  </div>
                  <button className="btn btn-primary" onClick={generateProtocol} disabled={generatingProtocol || !hasDataset}>
                    {generatingProtocol ? <Loader className="animate-spin" size={14} /> : <Beaker size={14} />}
                    {generatingProtocol ? 'Generating...' : 'Generate Protocol & ELN'}
                  </button>
                </div>

                {protocolDraft && (
                  <div style={{ marginBottom: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span className="badge badge-indigo">Protocol Draft</span>
                      <button 
                        className="btn btn-secondary" 
                        style={{ fontSize: '12px', padding: '6px 12px' }}
                        onClick={() => {
                          const blob = new Blob([protocolDraft], { type: 'text/markdown' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = 'protocol_draft.md';
                          a.click();
                        }}
                      >
                        <Download size={12} style={{ marginRight: '4px' }} />
                        Save Protocol
                      </button>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)', whiteSpace: 'pre-wrap', fontSize: '12px', lineHeight: '1.5', maxHeight: '300px', overflowY: 'auto' }}>
                      {protocolDraft}
                    </div>
                  </div>
                )}

                {elnEntry && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span className="badge badge-emerald">ELN Entry</span>
                      <button 
                        className="btn btn-secondary" 
                        style={{ fontSize: '12px', padding: '6px 12px' }}
                        onClick={() => {
                          const blob = new Blob([elnEntry], { type: 'text/markdown' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = 'eln_entry.md';
                          a.click();
                        }}
                      >
                        <Download size={12} style={{ marginRight: '4px' }} />
                        Save ELN
                      </button>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)', whiteSpace: 'pre-wrap', fontSize: '12px', lineHeight: '1.5', maxHeight: '300px', overflowY: 'auto' }}>
                      {elnEntry}
                    </div>
                  </div>
                )}

                {!protocolDraft && !elnEntry && (
                  <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)', fontSize: '12px' }}>
                    <Beaker size={24} style={{ marginBottom: '8px', opacity: 0.5 }} />
                    <div>No protocol or ELN generated yet</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab 5: Grounded Overseer Report */}
          {activeTab === 5 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div className="glass" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: '600' }}>📋 Grounded Research & Overseer Report</h3>
                    <p style={{ color: 'var(--text-secondary)' }}>Compile publication-grade reports grounding local findings with live web checks.</p>
                  </div>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button className="btn btn-primary" onClick={generateReport} disabled={generatingReport}>
                      {generatingReport ? <Loader className="animate-spin" size={14} /> : <Shield size={14} />}
                      {generatingReport ? 'Compiling...' : 'Generate Grounded Report'}
                    </button>
                    {overseerReport && (
                      <button className="btn btn-secondary" onClick={downloadReport}>
                        <Download size={14} /> Export Markdown
                      </button>
                    )}
                  </div>
                </div>

                {/* Workflow Trace */}
                {overseerReport && (
                  <div style={{ marginBottom: '20px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', fontWeight: '600' }}>
                      Workflow Trace
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '8px', padding: '16px', border: '1px solid var(--border-color)' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-emerald)' }} />
                          <span style={{ color: 'var(--text-secondary)' }}>Query Plan Built</span>
                          <span style={{ color: 'var(--text-muted)', marginLeft: 'auto' }}>✓ Complete</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-emerald)' }} />
                          <span style={{ color: 'var(--text-secondary)' }}>Papers Retrieved</span>
                          <span style={{ color: 'var(--text-muted)', marginLeft: 'auto' }}>{papers.length} papers</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-emerald)' }} />
                          <span style={{ color: 'var(--text-secondary)' }}>Claims Extracted</span>
                          <span style={{ color: 'var(--text-muted)', marginLeft: 'auto' }}>{claims.length} claims</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: consensusReport ? 'var(--accent-emerald)' : 'var(--text-muted)' }} />
                          <span style={{ color: 'var(--text-secondary)' }}>Consensus Analysis</span>
                          <span style={{ color: 'var(--text-muted)', marginLeft: 'auto' }}>{consensusReport ? '✓ Complete' : 'Pending'}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: protocolDraft ? 'var(--accent-emerald)' : 'var(--text-muted)' }} />
                          <span style={{ color: 'var(--text-secondary)' }}>Protocol Generated</span>
                          <span style={{ color: 'var(--text-muted)', marginLeft: 'auto' }}>{protocolDraft ? '✓ Complete' : 'Pending'}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-indigo)' }} />
                          <span style={{ color: 'var(--text-secondary)' }}>Grounded Report Compiled</span>
                          <span style={{ color: 'var(--text-muted)', marginLeft: 'auto' }}>✓ Complete</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Validation card */}
                {validationResults && (
                  <div style={{ background: validationResults.recommendation === 'proceed' ? 'rgba(16,185,129,0.04)' : 'rgba(244,63,94,0.04)', border: '1px solid', borderColor: validationResults.recommendation === 'proceed' ? 'rgba(16,185,129,0.15)' : 'rgba(244,63,94,0.15)', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
                    <div style={{ display: 'flex', gap: '30px', marginBottom: '12px' }}>
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Auditor Quality Score</div>
                        <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'white' }}>{validationResults.quality_score}/100</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Recommendation</div>
                        <div style={{ fontSize: '24px', fontWeight: 'bold', color: validationResults.recommendation === 'proceed' ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                          {validationResults.recommendation?.toUpperCase()}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Citations</div>
                        <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--accent-indigo)' }}>{validationResults.citation_count || papers.length}</div>
                      </div>
                    </div>
                    {validationResults.issues && validationResults.issues.length > 0 && (
                      <div style={{ marginTop: '12px', fontSize: '12px' }}>
                        <strong style={{ color: 'var(--accent-rose)' }}>Flagged Issues:</strong>
                        <ul style={{ paddingLeft: '20px', marginTop: '4px' }}>
                          {validationResults.issues.map((issue, idx) => <li key={idx}>{issue}</li>)}
                        </ul>
                      </div>
                    )}
                    {validationResults.web_sources && validationResults.web_sources.length > 0 && (
                      <div style={{ marginTop: '12px', fontSize: '12px' }}>
                        <strong style={{ color: 'var(--accent-indigo)' }}>Web Sources Verified:</strong>
                        <ul style={{ paddingLeft: '20px', marginTop: '4px' }}>
                          {validationResults.web_sources.map((source, idx) => (
                            <li key={idx}>
                              <a href={source.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-indigo)', textDecoration: 'underline' }}>
                                {source.title || source.url}
                              </a>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Cited Papers */}
                {overseerReport && papers.length > 0 && (
                  <div style={{ marginBottom: '20px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', fontWeight: '600' }}>
                      Cited Papers ({papers.length})
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {papers.map((paper, idx) => (
                        <span key={idx} className="badge badge-indigo" style={{ fontSize: '11px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          [{idx + 1}] {paper.title}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {overseerReport ? (
                  <div>
                    <div style={{ marginBottom: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span className="badge badge-emerald">✓ Report Generated</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{overseerReport.length} characters</span>
                      <span className="badge badge-indigo" style={{ fontSize: '11px' }}>Citation-Verified</span>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '20px', borderRadius: '8px', border: '1px solid var(--border-color)', whiteSpace: 'pre-wrap', fontSize: '13px', lineHeight: '1.6', maxHeight: '500px', overflowY: 'auto' }}>
                      {overseerReport}
                    </div>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    <Shield size={32} style={{ marginBottom: '12px', opacity: 0.5 }} />
                    <div>No report compiled yet</div>
                    <div style={{ fontSize: '12px', marginTop: '4px' }}>Click the button above to generate</div>
                  </div>
                )}
              </div>

              {/* Refinement input */}
              {overseerReport && (
                <div className="glass" style={{ padding: '20px' }}>
                  <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px' }}>🔄 Iterative Report Refiner</h4>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '12px' }}>Request specific edits, adjustments, or sections to expand. The agent will rewrite only target content.</p>
                  
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <input 
                      type="text" 
                      value={refinementFeedback} 
                      onChange={e => setRefinementFeedback(e.target.value)} 
                      placeholder="e.g., 'Expand section 3 on molecular targets of Metformin...'" 
                      style={{ flex: 1 }}
                    />
                    <button className="btn btn-secondary" onClick={refineReport} disabled={refiningReport || !refinementFeedback.trim()}>
                      {refiningReport ? <Loader className="animate-spin" size={14} /> : 'Apply Refinement'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const AppWithErrorBoundary = () => (
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);

export default AppWithErrorBoundary;
