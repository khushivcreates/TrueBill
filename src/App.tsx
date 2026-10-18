import React, { useState, useRef, useEffect } from 'react';
import {
  Zap,
  CheckCircle2,
  AlertTriangle,
  UploadCloud,
  FileText,
  File,
  RotateCcw,
  Copy,
  Check,
  ExternalLink,
  ShieldCheck,
  AlertCircle,
  HelpCircle,
  Sparkles,
  Info,
  Settings,
  X
} from 'lucide-react';

/* =========================================================================
   API CONFIGURATION
   Change these constants or use the UI settings to test your custom backend.
   ========================================================================= */
const API_URL = "http://localhost:8000";
const USE_MOCK = true;

/* =========================================================================
   DATA TYPES & INTERFACES
   ========================================================================= */
export interface CheckItem {
  item: string;
  status: "ok" | "warning";
  billed: number;
  expected: number;
  note: string;
}

export interface SourceItem {
  title: string;
  url: string;
  effective_date: string;
}

export interface AuditResult {
  checks: CheckItem[];
  explanation: string;
  sources: SourceItem[];
  uncertainties: string[];
  draft_complaint: string;
}

/* =========================================================================
   DEFAULT MOCK DATA
   Specified in project requirements (has 1 surcharge warning)
   ========================================================================= */
const DEFAULT_MOCK_DATA: AuditResult = {
  checks: [
    { item: "Units consumed", status: "ok", billed: 312, expected: 312, note: "" },
    { item: "Energy charge", status: "ok", billed: 1840, expected: 1840, note: "" },
    { item: "Fixed charge", status: "ok", billed: 250, expected: 250, note: "" },
    { item: "Surcharges", status: "warning", billed: 420, expected: 310, note: "Billed surcharge is higher than the official rate suggests." },
    { item: "Billing period", status: "ok", billed: 30, expected: 30, note: "" }
  ],
  explanation: "Your energy and fixed charges match the official tariff. The surcharge is Rs 110 higher than expected, which may be a billing error or a charge that is not in the tariff order we found.",
  sources: [
    { title: "Official tariff order (sample)", url: "https://www.derc.gov.in", effective_date: "2025-04-01" }
  ],
  uncertainties: ["Surcharge rule could not be confirmed from a single source."],
  draft_complaint: "Subject: Request for clarification on surcharge in my electricity bill\n\nRespected Sir/Madam,\n\nI would like clarification on the surcharge of Rs 420 on my latest bill. Based on the official tariff, I expected about Rs 310. Please explain this charge or correct it if it is an error.\n\nThank you."
};

/* Additional Verified Mock to showcase the green VERIFIED stamp when all checks pass */
const VERIFIED_SAMPLE_DATA: AuditResult = {
  checks: [
    { item: "Units consumed", status: "ok", billed: 245, expected: 245, note: "" },
    { item: "Energy charge", status: "ok", billed: 1420, expected: 1420, note: "Slab rates verified against DERC 2025 schedule" },
    { item: "Fixed charge", status: "ok", billed: 180, expected: 180, note: "Sanctioned load 2kW domestic" },
    { item: "PPAC (Fuel Surcharge)", status: "ok", billed: 284, expected: 284, note: "Regulatory PPAC surcharge matches 20.0% ceiling" },
    { item: "Electricity Duty (5%)", status: "ok", billed: 94, expected: 94, note: "State statutory municipal tax verified" },
    { item: "Billing period", status: "ok", billed: 31, expected: 31, note: "Meter reading cycle confirmed" }
  ],
  explanation: "All charges, slab breakdowns, fuel surcharges, and regulatory duties strictly conform to the approved DISCOM tariff order. Zero discrepancies detected. Every rupee billed is accurate.",
  sources: [
    { title: "DERC Domestic Tariff Order 2025-26", url: "https://www.derc.gov.in", effective_date: "2025-04-01" },
    { title: "Fuel Price Adjustment Schedule Q2", url: "https://www.derc.gov.in", effective_date: "2025-07-01" }
  ],
  uncertainties: [],
  draft_complaint: ""
};

/* =========================================================================
   API CALL FUNCTION
   All API interactions are encapsulated in this function so you can easily
   modify or point it to your backend service.
   ========================================================================= */
async function auditElectricityBill(
  file: File,
  useMock: boolean = USE_MOCK,
  apiUrl: string = API_URL,
  mockVariant: 'default' | 'verified' | 'error' = 'default'
): Promise<AuditResult> {
  // If mock mode is enabled:
  if (useMock) {
    // Wait 3 seconds to show the loading animation
    await new Promise((resolve) => setTimeout(resolve, 3000));

    // If user selected the error simulation sample or file name has 'corrupt'/'error'
    if (mockVariant === 'error' || file.name.toLowerCase().includes('error') || file.name.toLowerCase().includes('unreadable')) {
      throw new Error("We couldn't read this bill. Try a clearer photo or a PDF.");
    }

    if (mockVariant === 'verified' || file.name.toLowerCase().includes('verified')) {
      return VERIFIED_SAMPLE_DATA;
    }

    return DEFAULT_MOCK_DATA;
  }

  // Live Backend Call:
  const formData = new FormData();
  formData.append("file", file);

  const endpoint = `${apiUrl.replace(/\/$/, '')}/process`;
  
  const response = await fetch(endpoint, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let errorMsg = `Server error (${response.status})`;
    try {
      const errData = await response.json();
      if (errData && errData.message) errorMsg = errData.message;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }

  const result: AuditResult = await response.json();
  return result;
}

/* =========================================================================
   HELPER UTILITIES
   ========================================================================= */
function formatRupee(num: number): string {
  return '₹' + num.toLocaleString('en-IN');
}

function formatCheckValue(item: string, value: number): string {
  const lower = item.toLowerCase();
  if (lower.includes('unit')) {
    return `${value.toLocaleString('en-IN')} units`;
  }
  if (lower.includes('period') || lower.includes('day')) {
    return `${value.toLocaleString('en-IN')} days`;
  }
  return formatRupee(value);
}

export default function App() {
  // Application State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreviewUrl, setFilePreviewUrl] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  
  // Audit Flow States
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [auditResult, setAuditResult] = useState<AuditResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  
  // UI & Config States
  const [copied, setCopied] = useState(false);
  const [mockVariant, setMockVariant] = useState<'default' | 'verified' | 'error'>('default');
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [currentUseMock, setCurrentUseMock] = useState(USE_MOCK);
  const [currentApiUrl, setCurrentApiUrl] = useState(API_URL);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Loading Steps config
  const loadingSteps = [
    { title: "Reading your bill", desc: "Extracting units, slabs, meter readings & charges" },
    { title: "Fetching official tariff", desc: "Querying published DISCOM regulatory gazette" },
    { title: "Recalculating charges", desc: "Verifying arithmetic, fixed load & surcharge rules" },
    { title: "Writing explanation", desc: "Synthesizing transparent audit findings" }
  ];

  // Animated step progression during loading
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isLoading) {
      setLoadingStep(0);
      interval = setInterval(() => {
        setLoadingStep((prev) => {
          if (prev < loadingSteps.length - 1) {
            return prev + 1;
          }
          return prev;
        });
      }, 750); // evenly spreads 4 steps across ~3 seconds
    }
    return () => clearInterval(interval);
  }, [isLoading]);

  // Handle file selection
  const handleFileChange = (file: File) => {
    setSelectedFile(file);
    setErrorMessage(null);

    // Create thumbnail preview if image
    if (file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file);
      setFilePreviewUrl(url);
    } else {
      setFilePreviewUrl(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
      if (validTypes.includes(file.type) || file.name.match(/\.(jpg|jpeg|png|webp|pdf)$/i)) {
        handleFileChange(file);
      } else {
        setErrorMessage("Please upload an image (JPG, PNG) or PDF of your bill.");
      }
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  // Run the audit
  const handleAudit = async () => {
    if (!selectedFile) return;

    setIsLoading(true);
    setErrorMessage(null);
    setAuditResult(null);

    try {
      const result = await auditElectricityBill(
        selectedFile,
        currentUseMock,
        currentApiUrl,
        mockVariant
      );
      setAuditResult(result);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "We couldn't read this bill. Try a clearer photo or a PDF.";
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // Reset page
  const handleReset = () => {
    setSelectedFile(null);
    setFilePreviewUrl(null);
    setAuditResult(null);
    setErrorMessage(null);
    setIsLoading(false);
    setMockVariant('default');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Copy draft complaint
  const handleCopyComplaint = () => {
    if (!auditResult?.draft_complaint) return;
    navigator.clipboard.writeText(auditResult.draft_complaint);
    setCopied(true);
    setTimeout(() => setCopied(false), 2200);
  };

  // Select demo sample bill
  const handleSelectSample = (type: 'default' | 'verified' | 'error') => {
    setMockVariant(type);
    let sampleFile: File;
    if (type === 'default') {
      sampleFile = new window.File(["sample-derc-bill"], "Delhi_DISCOM_Domestic_Bill.pdf", { type: "application/pdf" });
    } else if (type === 'verified') {
      sampleFile = new window.File(["sample-verified-bill"], "BSES_Clean_Verified_Bill.pdf", { type: "application/pdf" });
    } else {
      sampleFile = new window.File(["blurred-photo"], "Unreadable_Blurry_Photo.jpg", { type: "image/jpeg" });
    }
    handleFileChange(sampleFile);
  };

  // Determine if all checks pass
  const isAllVerified = auditResult ? auditResult.checks.every(c => c.status === 'ok') : false;

  // Calculate totals
  const totalBilled = auditResult
    ? auditResult.checks
        .filter(c => !/unit|period|day/i.test(c.item))
        .reduce((acc, c) => acc + c.billed, 0)
    : 0;

  const totalExpected = auditResult
    ? auditResult.checks
        .filter(c => !/unit|period|day/i.test(c.item))
        .reduce((acc, c) => acc + c.expected, 0)
    : 0;

  const totalDifference = totalBilled - totalExpected;

  return (
    <div className="min-h-screen bg-[#0B1822] text-[#EFEAE0] flex flex-col justify-between selection:bg-[#F0A818]/30 selection:text-[#F0A818]">
      {/* Background Subtle Gradient & Grid */}
      <div className="fixed inset-0 pointer-events-none opacity-20">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-[#F0A818] rounded-full blur-[140px]" />
        <div className="absolute top-1/2 -right-40 w-96 h-96 bg-[#12A06A] rounded-full blur-[160px]" />
      </div>

      {/* Top Bar with Status / Dev Mode Settings */}
      <header className="relative z-10 w-full border-b border-[#EFEAE0]/10 bg-[#0B1822]/80 backdrop-blur-md">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono tracking-wider font-semibold bg-[#F0A818]/15 text-[#F0A818] border border-[#F0A818]/30">
              <Zap className="w-3 h-3 text-[#F0A818] fill-[#F0A818]" />
              AI ELECTRICITY BILL AUDITOR
            </span>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsConfigOpen(!isConfigOpen)}
              className="inline-flex items-center gap-1.5 text-xs font-mono text-[#EFEAE0]/70 hover:text-[#EFEAE0] transition-colors py-1 px-2.5 rounded border border-[#EFEAE0]/15 hover:border-[#EFEAE0]/30 bg-[#0B1822]"
              title="API & Mock settings"
            >
              <Settings className="w-3.5 h-3.5 text-[#F0A818]" />
              <span>{currentUseMock ? "Mode: Mock" : "Mode: Live API"}</span>
            </button>
          </div>
        </div>

        {/* Slide-down Settings Panel */}
        {isConfigOpen && (
          <div className="border-t border-[#EFEAE0]/10 bg-[#0e1f2c] px-4 py-4 text-xs font-mono">
            <div className="max-w-4xl mx-auto space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[#F0A818] flex items-center gap-1.5">
                  <Settings className="w-3.5 h-3.5" /> API Connection Settings
                </span>
                <button
                  onClick={() => setIsConfigOpen(false)}
                  className="text-[#EFEAE0]/60 hover:text-[#EFEAE0]"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                <div>
                  <label className="block text-[#EFEAE0]/70 mb-1">Audit Mode:</label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setCurrentUseMock(true)}
                      className={`flex-1 py-1.5 px-3 rounded border text-center transition-all ${
                        currentUseMock
                          ? "bg-[#F0A818] text-[#0B1822] font-bold border-[#F0A818]"
                          : "bg-transparent text-[#EFEAE0]/70 border-[#EFEAE0]/20 hover:border-[#EFEAE0]/40"
                      }`}
                    >
                      USE_MOCK = true
                    </button>
                    <button
                      type="button"
                      onClick={() => setCurrentUseMock(false)}
                      className={`flex-1 py-1.5 px-3 rounded border text-center transition-all ${
                        !currentUseMock
                          ? "bg-[#F0A818] text-[#0B1822] font-bold border-[#F0A818]"
                          : "bg-transparent text-[#EFEAE0]/70 border-[#EFEAE0]/20 hover:border-[#EFEAE0]/40"
                      }`}
                    >
                      USE_MOCK = false (Live)
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-[#EFEAE0]/70 mb-1">API_URL endpoint:</label>
                  <input
                    type="text"
                    value={currentApiUrl}
                    onChange={(e) => setCurrentApiUrl(e.target.value)}
                    disabled={currentUseMock}
                    className="w-full bg-[#0B1822] border border-[#EFEAE0]/20 rounded px-2.5 py-1.5 text-[#EFEAE0] focus:border-[#F0A818] focus:outline-none disabled:opacity-50"
                    placeholder="http://localhost:8000"
                  />
                </div>
              </div>
              <p className="text-[11px] text-[#EFEAE0]/50 pt-1">
                Post request to <code className="text-[#F0A818]">{currentApiUrl}/process</code> with multipart/form-data <code className="text-[#F0A818]">file</code> field.
              </p>
            </div>
          </div>
        )}
      </header>

      {/* Main Container */}
      <main className="relative z-10 max-w-4xl w-full mx-auto px-4 py-8 sm:py-12 flex-1 flex flex-col items-center">
        {/* 1. Header Section */}
        <div className="text-center mb-8 sm:mb-10 w-full">
          <div className="inline-flex items-center justify-center gap-1.5 mb-3 text-xs tracking-widest font-mono text-[#F0A818] uppercase font-semibold">
            <span className="w-2 h-2 rounded-full bg-[#F0A818] animate-pulse" />
            AI ELECTRICITY BILL AUDITOR
          </div>

          <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight mb-3 font-headline">
            <span className="text-[#EFEAE0]">True</span>
            <span className="text-[#F0A818]">Bill</span>
          </h1>

          <p className="text-base sm:text-lg text-[#EFEAE0]/80 font-medium tracking-wide">
            Every Bill. Every Rupee. Verified.
          </p>

          <p className="mt-2 text-xs sm:text-sm text-[#EFEAE0]/55 max-w-lg mx-auto">
            Cross-checks your power bill against state electricity regulatory tariffs, unit slab calculations, fixed demand quotas, and fuel surcharges.
          </p>
        </div>

        {/* 2. Upload Section (Visible when not showing result) */}
        {!auditResult && !isLoading && (
          <div className="w-full max-w-xl mx-auto space-y-6">
            {/* Quick Demo Sample Selector */}
            <div className="bg-[#0B1822] border border-[#EFEAE0]/15 rounded-xl p-3.5 text-xs">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[#EFEAE0]/70 font-mono flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-[#F0A818]" />
                  Need a sample bill to test right away?
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => handleSelectSample('default')}
                  className={`px-2.5 py-1.5 rounded-lg border text-left transition-all font-mono text-[11px] flex flex-col justify-between ${
                    mockVariant === 'default' && selectedFile
                      ? "bg-[#F0A818]/15 border-[#F0A818] text-[#F0A818]"
                      : "bg-[#EFEAE0]/5 border-[#EFEAE0]/10 hover:border-[#EFEAE0]/30 text-[#EFEAE0]/80"
                  }`}
                >
                  <span className="font-semibold">⚠️ Bill with Surcharge</span>
                  <span className="text-[10px] text-[#EFEAE0]/50 mt-0.5">Tests warning row</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleSelectSample('verified')}
                  className={`px-2.5 py-1.5 rounded-lg border text-left transition-all font-mono text-[11px] flex flex-col justify-between ${
                    mockVariant === 'verified' && selectedFile
                      ? "bg-[#12A06A]/15 border-[#12A06A] text-[#12A06A]"
                      : "bg-[#EFEAE0]/5 border-[#EFEAE0]/10 hover:border-[#EFEAE0]/30 text-[#EFEAE0]/80"
                  }`}
                >
                  <span className="font-semibold">✅ Clean Bill</span>
                  <span className="text-[10px] text-[#EFEAE0]/50 mt-0.5">Triggers stamp</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleSelectSample('error')}
                  className={`px-2.5 py-1.5 rounded-lg border text-left transition-all font-mono text-[11px] flex flex-col justify-between ${
                    mockVariant === 'error' && selectedFile
                      ? "bg-[#E5533D]/15 border-[#E5533D] text-[#E5533D]"
                      : "bg-[#EFEAE0]/5 border-[#EFEAE0]/10 hover:border-[#EFEAE0]/30 text-[#EFEAE0]/80"
                  }`}
                >
                  <span className="font-semibold">❌ Corrupt Scan</span>
                  <span className="text-[10px] text-[#EFEAE0]/50 mt-0.5">Tests error state</span>
                </button>
              </div>
            </div>

            {/* Drag & Drop Box */}
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`relative border-2 border-dashed rounded-2xl p-8 sm:p-10 text-center cursor-pointer transition-all duration-200 group ${
                isDragging
                  ? "border-[#F0A818] bg-[#F0A818]/10 scale-[1.01]"
                  : selectedFile
                  ? "border-[#12A06A]/50 bg-[#12A06A]/5 hover:border-[#12A06A]"
                  : "border-[#EFEAE0]/25 bg-[#EFEAE0]/5 hover:border-[#F0A818]/70 hover:bg-[#EFEAE0]/8"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,application/pdf"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileChange(e.target.files[0]);
                  }
                }}
              />

              {/* Display selected file preview or icon */}
              {selectedFile ? (
                <div className="flex flex-col items-center">
                  {filePreviewUrl ? (
                    <div className="relative mb-3 w-28 h-28 rounded-lg overflow-hidden border border-[#EFEAE0]/20 shadow-lg">
                      <img
                        src={filePreviewUrl}
                        alt="Bill preview"
                        className="w-full h-full object-cover"
                      />
                    </div>
                  ) : (
                    <div className="w-14 h-14 rounded-2xl bg-[#12A06A]/20 flex items-center justify-center mb-3 text-[#12A06A] border border-[#12A06A]/30">
                      <FileText className="w-7 h-7" />
                    </div>
                  )}

                  <div className="font-mono text-sm font-semibold text-[#EFEAE0] flex items-center gap-1.5 max-w-full px-2 truncate">
                    <CheckCircle2 className="w-4 h-4 text-[#12A06A] shrink-0" />
                    <span className="truncate">{selectedFile.name}</span>
                  </div>
                  <div className="text-xs text-[#EFEAE0]/50 font-mono mt-1">
                    {(selectedFile.size / 1024).toFixed(1)} KB · Click or drag to replace
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <div className="w-16 h-16 rounded-2xl bg-[#F0A818]/10 border border-[#F0A818]/25 flex items-center justify-center mb-4 text-[#F0A818] group-hover:scale-110 transition-transform">
                    <UploadCloud className="w-8 h-8" />
                  </div>
                  <p className="text-base sm:text-lg font-semibold text-[#EFEAE0] mb-1 font-headline">
                    Drop your electricity bill here, or <span className="text-[#F0A818] underline underline-offset-4">browse</span>
                  </p>
                  <p className="text-xs text-[#EFEAE0]/60 font-mono">
                    Supports JPG, PNG images and PDF documents
                  </p>
                </div>
              )}
            </div>

            {/* Error Message if any */}
            {errorMessage && (
              <div className="bg-[#E5533D]/15 border border-[#E5533D]/40 rounded-xl p-4 flex items-start gap-3 text-[#EFEAE0] animate-fadeIn">
                <AlertCircle className="w-5 h-5 text-[#E5533D] shrink-0 mt-0.5" />
                <div className="flex-1 text-sm">
                  <p className="font-semibold text-[#E5533D]">Audit Failed</p>
                  <p className="text-[#EFEAE0]/80 mt-0.5">{errorMessage}</p>
                  <button
                    type="button"
                    onClick={handleReset}
                    className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#E5533D]/20 hover:bg-[#E5533D]/30 text-[#E5533D] border border-[#E5533D]/40 text-xs font-mono font-medium transition-colors"
                  >
                    <RotateCcw className="w-3.5 h-3.5" /> Try a clearer photo or a PDF
                  </button>
                </div>
              </div>
            )}

            {/* Audit Button & Privacy Note */}
            <div className="flex flex-col items-center gap-3 pt-2">
              <button
                type="button"
                disabled={!selectedFile}
                onClick={handleAudit}
                className="w-full sm:w-auto min-w-[240px] px-8 py-3.5 rounded-xl font-headline font-bold text-base tracking-wide bg-[#F0A818] hover:bg-[#f3b432] active:scale-[0.98] text-[#0B1822] shadow-[0_0_25px_rgba(240,168,24,0.35)] transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none flex items-center justify-center gap-2 cursor-pointer"
              >
                <Zap className="w-5 h-5 fill-[#0B1822]" />
                Audit my bill
              </button>

              <div className="flex items-center gap-1.5 text-xs text-[#EFEAE0]/50 font-mono">
                <ShieldCheck className="w-3.5 h-3.5 text-[#12A06A]" />
                <span>Your bill is only used to run this audit.</span>
              </div>
            </div>
          </div>
        )}

        {/* 3. Loading State (Animated progress list) */}
        {isLoading && (
          <div className="w-full max-w-md mx-auto my-auto py-8">
            <div className="bg-[#0B1822] border border-[#EFEAE0]/20 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
              <div className="text-center mb-6">
                <div className="w-12 h-12 mx-auto rounded-full bg-[#F0A818]/15 border border-[#F0A818]/40 flex items-center justify-center mb-3">
                  <Zap className="w-6 h-6 text-[#F0A818] animate-bounce" />
                </div>
                <h3 className="text-xl font-bold font-headline text-[#EFEAE0]">Auditing Your Bill</h3>
                <p className="text-xs font-mono text-[#EFEAE0]/60 mt-1">Cross-verifying every rupee against tariff orders</p>
              </div>

              {/* Progress ticks list */}
              <div className="space-y-4">
                {loadingSteps.map((step, idx) => {
                  const isDone = loadingStep > idx;
                  const isCurrent = loadingStep === idx;
                  const isPending = loadingStep < idx;

                  return (
                    <div
                      key={step.title}
                      className={`flex items-start gap-3.5 p-3 rounded-xl transition-all duration-300 ${
                        isCurrent
                          ? "bg-[#F0A818]/10 border border-[#F0A818]/30 scale-[1.02]"
                          : isDone
                          ? "bg-[#12A06A]/10 border border-[#12A06A]/20"
                          : "opacity-40"
                      }`}
                    >
                      <div className="mt-0.5 shrink-0">
                        {isDone ? (
                          <div className="w-5 h-5 rounded-full bg-[#12A06A] text-[#0B1822] flex items-center justify-center">
                            <Check className="w-3.5 h-3.5 stroke-[3]" />
                          </div>
                        ) : isCurrent ? (
                          <div className="w-5 h-5 rounded-full border-2 border-[#F0A818] border-t-transparent animate-spin" />
                        ) : (
                          <div className="w-5 h-5 rounded-full border border-[#EFEAE0]/30 flex items-center justify-center text-[10px] font-mono">
                            {idx + 1}
                          </div>
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <p
                          className={`text-sm font-semibold ${
                            isCurrent
                              ? "text-[#F0A818]"
                              : isDone
                              ? "text-[#12A06A]"
                              : "text-[#EFEAE0]/70"
                          }`}
                        >
                          {step.title}
                        </p>
                        <p className="text-xs text-[#EFEAE0]/60 mt-0.5">{step.desc}</p>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="mt-6 pt-4 border-t border-[#EFEAE0]/10 text-center">
                <span className="text-[11px] font-mono text-[#EFEAE0]/50">
                  Step {Math.min(loadingStep + 1, 4)} of 4 · Auditing rules & formulas
                </span>
              </div>
            </div>
          </div>
        )}

        {/* 4. Result Section */}
        {auditResult && !isLoading && (
          <div className="w-full max-w-2xl mx-auto space-y-8 animate-fadeIn">
            {/* Top Action Bar */}
            <div className="flex items-center justify-between pb-2">
              <span className="text-xs font-mono text-[#EFEAE0]/70 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-[#12A06A]" />
                Audit Report Completed
              </span>

              <button
                type="button"
                onClick={handleReset}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#EFEAE0]/20 hover:border-[#F0A818] bg-[#0B1822] hover:bg-[#F0A818]/10 text-xs font-mono font-medium text-[#EFEAE0] transition-colors cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5 text-[#F0A818]" />
                Check another bill
              </button>
            </div>

            {/* 4.a RECEIPT CARD with scalloped bottom edge */}
            <div className="relative filter drop-shadow-2xl">
              <div className="bg-[#EFEAE0] text-[#0B1822] rounded-t-2xl p-6 sm:p-8 relative">
                {/* Decorative subtle texture */}
                <div
                  className="absolute inset-0 pointer-events-none opacity-[0.03] rounded-t-2xl"
                  style={{
                    backgroundImage: `radial-gradient(#000 1px, transparent 1px)`,
                    backgroundSize: '16px 16px'
                  }}
                />

                {/* VERIFIED Stamp Overlay (Visible when all checks pass) */}
                {isAllVerified && (
                  <div className="absolute top-6 right-6 sm:top-8 sm:right-8 z-20 pointer-events-none animate-stamp">
                    <div className="relative w-28 h-28 sm:w-32 sm:h-32 rounded-full border-4 border-[#12A06A] flex flex-col items-center justify-center p-2 text-[#12A06A] font-headline font-extrabold uppercase tracking-widest shadow-sm bg-[#EFEAE0]/80 backdrop-blur-xs">
                      {/* Inner dashed ring */}
                      <div className="absolute inset-1.5 rounded-full border-2 border-dashed border-[#12A06A]/70" />
                      <span className="text-[9px] font-mono tracking-widest opacity-80">TRUEBILL</span>
                      <span className="text-lg sm:text-xl font-black tracking-tight leading-none my-0.5">VERIFIED</span>
                      <div className="w-8 h-0.5 bg-[#12A06A] my-0.5" />
                      <span className="text-[8px] font-mono tracking-wider">100% ACCURATE</span>
                    </div>
                  </div>
                )}

                {/* Receipt Header */}
                <div className="border-b-2 border-[#0B1822]/15 pb-4 mb-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-[11px] font-mono uppercase tracking-widest text-[#0B1822]/60 font-semibold">
                        OFFICIAL VERIFICATION SLIP
                      </p>
                      <h2 className="text-xl sm:text-2xl font-black font-headline tracking-tight text-[#0B1822] mt-0.5">
                        ELECTRICITY BILL / AUDIT RESULT
                      </h2>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-mono text-[#0B1822]/70">
                    <span>Audit Ref: TB-{(Math.random() * 90000 + 10000).toFixed(0)}</span>
                    <span>•</span>
                    <span>Date: {new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
                    <span>•</span>
                    <span className="font-semibold text-[#0B1822]">
                      {isAllVerified ? (
                        <span className="text-[#12A06A]">All {auditResult.checks.length} Checks Passed</span>
                      ) : (
                        <span className="text-[#E5533D]">
                          {auditResult.checks.filter(c => c.status === 'warning').length} Discrepancy Found
                        </span>
                      )}
                    </span>
                  </div>
                </div>

                {/* Checks List */}
                <div className="space-y-4">
                  <div className="text-[11px] font-mono uppercase tracking-wider text-[#0B1822]/50 grid grid-cols-12 pb-1 border-b border-[#0B1822]/10">
                    <span className="col-span-5 sm:col-span-6">Line Item</span>
                    <span className="col-span-5 sm:col-span-4 text-right">Audit Comparison</span>
                    <span className="col-span-2 text-right">Status</span>
                  </div>

                  {auditResult.checks.map((check, idx) => {
                    const isOk = check.status === "ok";
                    const isUnitOrPeriod = /unit|period|day/i.test(check.item);
                    const formattedBilled = `₹${check.billed.toLocaleString('en-IN')}`;
                    const formattedExpected = `₹${check.expected.toLocaleString('en-IN')}`;
                    
                    return (
                      <div
                        key={idx}
                        className={`py-2 px-1 rounded-lg transition-colors ${
                          !isOk ? "bg-[#E5533D]/10 -mx-1 px-2 border border-[#E5533D]/30" : ""
                        }`}
                      >
                        <div className="grid grid-cols-12 items-baseline gap-2">
                          {/* Item Name */}
                          <div className="col-span-5 sm:col-span-6 font-semibold text-sm sm:text-base text-[#0B1822] flex items-center gap-1.5">
                            <span>{check.item}</span>
                          </div>

                          {/* Billed ₹X vs Expected ₹Y */}
                          <div className="col-span-5 sm:col-span-4 text-right font-mono text-xs sm:text-sm">
                            <span className="text-[#0B1822]/70">Billed </span>
                            <span className="font-bold text-[#0B1822]">{formattedBilled}</span>
                            <span className="text-[#0B1822]/70"> vs Expected </span>
                            <span className="font-bold text-[#0B1822]">{formattedExpected}</span>
                            {isUnitOrPeriod && (
                              <div className="text-[10px] text-[#0B1822]/60 font-mono">
                                ({check.billed} {/period|day/i.test(check.item) ? 'days' : 'units'})
                              </div>
                            )}
                          </div>

                          {/* Status Icon */}
                          <div className="col-span-2 flex justify-end items-center">
                            {isOk ? (
                              <span
                                className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-[#12A06A]/15 text-[#12A06A]"
                                title="Verified OK"
                              >
                                <Check className="w-4 h-4 stroke-[3]" />
                              </span>
                            ) : (
                              <span
                                className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-[#E5533D]/20 text-[#E5533D]"
                                title="Warning: Discrepancy detected"
                              >
                                <AlertTriangle className="w-4 h-4 stroke-[2.5]" />
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Note under row */}
                        {check.note && (
                          <div className="mt-1 text-xs text-[#E5533D] font-mono flex items-start gap-1 pl-0.5">
                            <span className="text-xs">↳</span>
                            <span className="leading-tight">{check.note}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Receipt Subtotals & Summary */}
                <div className="mt-6 pt-4 border-t-2 border-[#0B1822]/15">
                  <div className="flex items-center justify-between text-sm sm:text-base font-bold text-[#0B1822] mb-1">
                    <span className="font-headline uppercase tracking-wider">Total Billed Charges</span>
                    <span className="font-mono text-base sm:text-lg">{formatRupee(totalBilled)}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs sm:text-sm text-[#0B1822]/70 font-mono mb-2">
                    <span>Tariff Expected Amount</span>
                    <span>{formatRupee(totalExpected)}</span>
                  </div>

                  {totalDifference !== 0 && (
                    <div className="flex items-center justify-between text-xs sm:text-sm font-mono pt-2 border-t border-[#0B1822]/10 font-bold">
                      <span className={totalDifference > 0 ? "text-[#E5533D]" : "text-[#12A06A]"}>
                        {totalDifference > 0 ? "Potential Overcharge" : "Undercharged Variance"}
                      </span>
                      <span className={totalDifference > 0 ? "text-[#E5533D]" : "text-[#12A06A]"}>
                        {totalDifference > 0 ? `+${formatRupee(totalDifference)}` : formatRupee(totalDifference)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Tear barcode aesthetic */}
                <div className="mt-6 pt-4 border-t border-dashed border-[#0B1822]/20 flex items-center justify-between opacity-50 font-mono text-[10px]">
                  <span>AUTHENTICATED BY TRUEBILL ENGINE</span>
                  <div className="h-4 flex items-end gap-[2px]">
                    {[4, 2, 5, 1, 3, 6, 2, 4, 3, 5, 2, 4, 1, 6, 3, 2, 5].map((h, i) => (
                      <span
                        key={i}
                        className="bg-[#0B1822] inline-block"
                        style={{ width: i % 3 === 0 ? '2px' : '1px', height: `${h * 2.5}px` }}
                      />
                    ))}
                  </div>
                </div>
              </div>

              {/* Scalloped / Torn Bottom Edge SVG */}
              <div className="relative w-full overflow-hidden leading-none -mt-[1px] select-none">
                <svg
                  className="w-full text-[#EFEAE0] fill-current h-4 sm:h-5 block"
                  viewBox="0 0 1200 20"
                  preserveAspectRatio="none"
                >
                  <defs>
                    <pattern id="receipt-scallop-pattern" width="24" height="20" patternUnits="userSpaceOnUse">
                      <path d="M 0,0 L 0,4 C 6,18 18,18 24,4 L 24,0 Z" fill="#EFEAE0" />
                    </pattern>
                  </defs>
                  <rect width="1200" height="20" fill="url(#receipt-scallop-pattern)" />
                </svg>
              </div>
            </div>

            {/* 4.b "In plain language" card showing explanation */}
            <div className="bg-[#EFEAE0] text-[#0B1822] rounded-2xl p-6 sm:p-7 shadow-lg border border-[#EFEAE0]/20">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-[#0B1822]/10 flex items-center justify-center text-[#0B1822]">
                  <Info className="w-4 h-4 text-[#F0A818]" />
                </div>
                <h3 className="text-base sm:text-lg font-bold font-headline text-[#0B1822]">
                  In Plain Language
                </h3>
              </div>
              <p className="text-sm sm:text-base text-[#0B1822]/85 leading-relaxed font-sans">
                {auditResult.explanation}
              </p>
            </div>

            {/* 4.c "Uncertainties" card (hidden if empty) */}
            {auditResult.uncertainties && auditResult.uncertainties.length > 0 && (
              <div className="bg-[#E5533D]/10 border border-[#E5533D]/30 rounded-2xl p-5 sm:p-6 text-[#EFEAE0]">
                <div className="flex items-center gap-2 mb-3">
                  <AlertCircle className="w-5 h-5 text-[#E5533D]" />
                  <h3 className="text-sm sm:text-base font-bold font-headline text-[#E5533D] uppercase tracking-wide">
                    Uncertainties & Limitations
                  </h3>
                </div>
                <ul className="space-y-2">
                  {auditResult.uncertainties.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs sm:text-sm text-[#EFEAE0]/85 font-mono">
                      <span className="text-[#E5533D] font-bold">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 4.d "Official sources" card */}
            {auditResult.sources && auditResult.sources.length > 0 && (
              <div className="bg-[#0B1822] border border-[#EFEAE0]/15 rounded-2xl p-5 sm:p-6 text-[#EFEAE0]">
                <div className="flex items-center gap-2 mb-3">
                  <ShieldCheck className="w-4 h-4 text-[#12A06A]" />
                  <h3 className="text-sm sm:text-base font-bold font-headline text-[#EFEAE0]">
                    Official Sources & Tariff Orders
                  </h3>
                </div>
                <div className="divide-y divide-[#EFEAE0]/10">
                  {auditResult.sources.map((src, idx) => (
                    <div key={idx} className="py-2.5 flex items-center justify-between gap-4 first:pt-0 last:pb-0">
                      <div>
                        <p className="text-sm font-semibold text-[#EFEAE0]">{src.title}</p>
                        <p className="text-xs text-[#EFEAE0]/50 font-mono mt-0.5">
                          Effective Date: {src.effective_date}
                        </p>
                      </div>
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#EFEAE0]/5 hover:bg-[#F0A818]/15 text-[#F0A818] border border-[#EFEAE0]/15 hover:border-[#F0A818]/40 text-xs font-mono font-medium transition-colors shrink-0"
                      >
                        <span>View Source</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 4.e "Draft clarification request" card (hidden if empty) */}
            {auditResult.draft_complaint && auditResult.draft_complaint.trim().length > 0 && (
              <div className="bg-[#0B1822] border border-[#F0A818]/30 rounded-2xl p-5 sm:p-6 text-[#EFEAE0] relative">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-[#F0A818]" />
                    <h3 className="text-sm sm:text-base font-bold font-headline text-[#EFEAE0]">
                      Draft Clarification Request
                    </h3>
                  </div>

                  <button
                    type="button"
                    onClick={handleCopyComplaint}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#F0A818] hover:bg-[#f3b432] text-[#0B1822] font-mono font-bold text-xs transition-transform active:scale-95 cursor-pointer shadow-sm"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3.5 h-3.5 stroke-[3]" />
                        <span>Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy Letter</span>
                      </>
                    )}
                  </button>
                </div>

                <p className="text-xs text-[#EFEAE0]/60 mb-2 font-mono">
                  Ready to send to your electricity distribution company (DISCOM) consumer grievance cell:
                </p>

                <div className="bg-[#0e2130] border border-[#EFEAE0]/15 rounded-xl p-4 font-mono text-xs sm:text-sm text-[#EFEAE0]/90 whitespace-pre-wrap leading-relaxed select-all">
                  {auditResult.draft_complaint}
                </div>
              </div>
            )}

            {/* 4.f Check Another Bill Footer Button */}
            <div className="flex justify-center pt-2">
              <button
                type="button"
                onClick={handleReset}
                className="px-6 py-3 rounded-xl border border-[#F0A818] hover:bg-[#F0A818]/10 text-[#F0A818] font-headline font-bold text-sm tracking-wide flex items-center gap-2 transition-colors cursor-pointer"
              >
                <RotateCcw className="w-4 h-4" />
                Check another bill
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="relative z-10 w-full border-t border-[#EFEAE0]/10 py-6 text-center text-xs font-mono text-[#EFEAE0]/60">
        <div className="max-w-4xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>TrueBill · AI Electricity Bill Auditor</span>
          <span className="text-[#F0A818] font-medium">Team LuvKush · Lakshay Verma | Khushi Verma</span>
          <span>Every Bill. Every Rupee. Verified.</span>
        </div>
      </footer>
    </div>
  );
}
