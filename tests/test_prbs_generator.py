import cocotb
from cocotb.triggers import RisingEdge, FallingEdge, Timer
from cocotb.clock import Clock
import random


class PRBSReferenceModel:
    """Reference model for PRBS generation"""
    
    def __init__(self, prbs_type):
        self.prbs_type = prbs_type
        self.lfsr = 0
        self._setup_polynomial()
    
    def _setup_polynomial(self):
        """Setup polynomial parameters based on PRBS type"""
        if self.prbs_type == 0:  # PRBS7
            self.width = 7
            self.mask = 0x7F
            self.tap1 = 6
            self.tap2 = 5
            self.output_bit = 6
        elif self.prbs_type == 1:  # PRBS9
            self.width = 9
            self.mask = 0x1FF
            self.tap1 = 8
            self.tap2 = 4
            self.output_bit = 8
        elif self.prbs_type == 2:  # PRBS15
            self.width = 15
            self.mask = 0x7FFF
            self.tap1 = 14
            self.tap2 = 13
            self.output_bit = 14
        elif self.prbs_type == 3:  # PRBS31
            self.width = 31
            self.mask = 0x7FFFFFFF
            self.tap1 = 30
            self.tap2 = 27
            self.output_bit = 30
    
    def _shift_lfsr(self):
        """Shift LFSR once and return output bit"""
        output = (self.lfsr >> self.output_bit) & 1
        feedback = ((self.lfsr >> self.tap1) ^ (self.lfsr >> self.tap2)) & 1
        self.lfsr = ((self.lfsr << 1) | feedback) & self.mask
        return output
    
    def process_seed(self, seed):
        """Process seed through 8 iterations (as done in hardware)"""
        self.lfsr = seed & self.mask
        # Run 8 iterations
        for _ in range(8):
            self._shift_lfsr()
        return self.lfsr
    
    def generate_8_bits(self):
        """Generate 8 bits from current LFSR state"""
        output = 0
        for i in range(8):
            bit = self._shift_lfsr()
            output = (output << 1) | bit
        return output


async def reset_dut(dut):
    """Reset the DUT"""
    dut.reset_n.value = 0
    dut.enable.value = 0
    dut.load.value = 0
    dut.prbs_type.value = 0
    dut.prbs_seed.value = 0
    await Timer(10, units="ns")
    dut.reset_n.value = 1
    await RisingEdge(dut.clock)


async def load_seed(dut, prbs_type, seed):
    """Load seed into PRBS generator"""
    dut.prbs_type.value = prbs_type
    dut.prbs_seed.value = seed
    await Timer(10, units="ns")  # Wait for seed to settle
    dut.load.value = 1
    await RisingEdge(dut.clock)
    dut.load.value = 0
    await RisingEdge(dut.clock)


@cocotb.test()
async def test_reset(dut):
    """Test reset functionality"""
    # Start clock
    cocotb.start_soon(Clock(dut.clock, 10, units="ns").start())
    
    # Apply reset
    dut.reset_n.value = 0
    dut.enable.value = 1
    dut.load.value = 0
    dut.prbs_type.value = 0
    dut.prbs_seed.value = 0x12345678
    await Timer(20, units="ns")
    
    # Check outputs are zero during reset
    assert dut.prbs_out.value.integer == 0, "Output should be zero during reset"
    
    # Release reset
    dut.reset_n.value = 1
    await RisingEdge(dut.clock)
    
    # Output should still be zero until seed is loaded and enabled
    assert dut.prbs_out.value.integer == 0, "Output should be zero after reset"
    
    dut._log.info("Reset test PASSED ✅")


@cocotb.test()
async def test_seed_load_prbs7(dut):
    """Test seed loading for PRBS7"""
    cocotb.start_soon(Clock(dut.clock, 10, units="ns").start())
    
    await reset_dut(dut)
    
    # Test PRBS7 with known seed
    prbs_type = 0
    seed = 0x7F  # All ones for PRBS7
    
    # Create reference model
    ref_model = PRBSReferenceModel(prbs_type)
    processed_seed = ref_model.process_seed(seed)
    expected_first_output = ref_model.generate_8_bits()
    
    # Load seed
    await load_seed(dut, prbs_type, seed)
    
    # Enable and check first output
    dut.enable.value = 1
    await RisingEdge(dut.clock)
    
    actual_output = dut.prbs_out.value.integer
    assert actual_output == expected_first_output, (
        f"First output mismatch after seed load\n"
        f"Expected: {hex(expected_first_output)}\n"
        f"Got: {hex(actual_output)}\n"
        f"Seed: {hex(seed)}, Processed seed: {hex(processed_seed)}"
    )
    
    dut._log.info(f"Seed load test PASSED ✅ (PRBS7, seed={hex(seed)})")


@cocotb.test()
async def test_seed_load_all_types(dut):
    """Test seed loading for all PRBS types"""
    cocotb.start_soon(Clock(dut.clock, 10, units="ns").start())
    
    test_cases = [
        (0, 0x7F, "PRBS7"),
        (1, 0x1FF, "PRBS9"),
        (2, 0x7FFF, "PRBS15"),
        (3, 0x7FFFFFFF, "PRBS31"),
    ]
    
    for prbs_type, seed, name in test_cases:
        await reset_dut(dut)
        
        # Create reference model
        ref_model = PRBSReferenceModel(prbs_type)
        processed_seed = ref_model.process_seed(seed)
        expected_first_output = ref_model.generate_8_bits()
        
        # Load seed
        await load_seed(dut, prbs_type, seed)
        
        # Enable and check first output
        dut.enable.value = 1
        await RisingEdge(dut.clock)
        
        actual_output = dut.prbs_out.value.integer
        assert actual_output == expected_first_output, (
            f"{name} first output mismatch after seed load\n"
            f"Expected: {hex(expected_first_output)}\n"
            f"Got: {hex(actual_output)}\n"
            f"Seed: {hex(seed)}, Processed seed: {hex(processed_seed)}"
        )
        
        dut._log.info(f"{name} seed load test PASSED ✅")
    
    dut._log.info("All PRBS types seed load test PASSED ✅")


@cocotb.test()
async def test_prbs_sequence_prbs7(dut):
    """Test PRBS sequence generation for PRBS7"""
    cocotb.start_soon(Clock(dut.clock, 10, units="ns").start())
    
    await reset_dut(dut)
    
    prbs_type = 0
    seed = 0x01  # Simple seed for PRBS7
    
    # Create reference model
    ref_model = PRBSReferenceModel(prbs_type)
    ref_model.process_seed(seed)
    
    # Load seed
    await load_seed(dut, prbs_type, seed)
    
    # Enable and check multiple outputs
    dut.enable.value = 1
    
    num_outputs = 20
    for i in range(num_outputs):
        await RisingEdge(dut.clock)
        expected_output = ref_model.generate_8_bits()
        actual_output = dut.prbs_out.value.integer
        
        assert actual_output == expected_output, (
            f"Output mismatch at cycle {i}\n"
            f"Expected: {hex(expected_output)}\n"
            f"Got: {hex(actual_output)}"
        )
    
    dut._log.info(f"PRBS7 sequence test PASSED ✅ ({num_outputs} cycles)")


@cocotb.test()
async def test_prbs_sequence_all_types(dut):
    """Test PRBS sequence generation for all types"""
    cocotb.start_soon(Clock(dut.clock, 10, units="ns").start())
    
    test_cases = [
        (0, 0x01, "PRBS7"),
        (1, 0x01, "PRBS9"),
        (2, 0x0001, "PRBS15"),
        (3, 0x00000001, "PRBS31"),
    ]
    
    for prbs_type, seed, name in test_cases:
        await reset_dut(dut)
        
        # Create reference model
        ref_model = PRBSReferenceModel(prbs_type)
        ref_model.process_seed(seed)
        
        # Load seed
        await load_seed(dut, prbs_type, seed)
        
        # Enable and check multiple outputs
        dut.enable.value = 1
        
        num_outputs = 10
        for i in range(num_outputs):
            await RisingEdge(dut.clock)
            expected_output = ref_model.generate_8_bits()
            actual_output = dut.prbs_out.value.integer
            
            assert actual_output == expected_output, (
                f"{name} output mismatch at cycle {i}\n"
                f"Expected: {hex(expected_output)}\n"
                f"Got: {hex(actual_output)}"
            )
        
        dut._log.info(f"{name} sequence test PASSED ✅")
    
    dut._log.info("All PRBS types sequence test PASSED ✅")


@cocotb.test()
async def test_enable_disable(dut):
    """Test enable/disable functionality"""
    cocotb.start_soon(Clock(dut.clock, 10, units="ns").start())
    
    await reset_dut(dut)
    
    prbs_type = 0
    seed = 0x7F
    
    # Create reference model
    ref_model = PRBSReferenceModel(prbs_type)
    ref_model.process_seed(seed)
    
    # Load seed
    await load_seed(dut, prbs_type, seed)
    
    # Enable and get first output
    dut.enable.value = 1
    await RisingEdge(dut.clock)
    first_output = dut.prbs_out.value.integer
    expected_second = ref_model.generate_8_bits()
    
    # Disable - output should remain stable
    dut.enable.value = 0
    await RisingEdge(dut.clock)
    assert dut.prbs_out.value.integer == first_output, "Output should remain stable when disabled"
    
    # Wait a few cycles - output should still be stable
    for _ in range(5):
        await RisingEdge(dut.clock)
        assert dut.prbs_out.value.integer == first_output, "Output should remain stable when disabled"
    
    # Re-enable - should continue from where it left off
    dut.enable.value = 1
    await RisingEdge(dut.clock)
    assert dut.prbs_out.value.integer == expected_second, "Output should continue after re-enable"
    
    dut._log.info("Enable/disable test PASSED ✅")


@cocotb.test()
async def test_random_seeds(dut):
    """Test with random seeds for all PRBS types"""
    cocotb.start_soon(Clock(dut.clock, 10, units="ns").start())
    
    random.seed(42)  # For reproducibility
    
    for prbs_type in range(4):
        await reset_dut(dut)
        
        # Generate random seed within valid range
        if prbs_type == 0:
            seed = random.randint(1, 0x7F)
        elif prbs_type == 1:
            seed = random.randint(1, 0x1FF)
        elif prbs_type == 2:
            seed = random.randint(1, 0x7FFF)
        else:  # PRBS31
            seed = random.randint(1, 0x7FFFFFFF)
        
        # Create reference model
        ref_model = PRBSReferenceModel(prbs_type)
        ref_model.process_seed(seed)
        
        # Load seed
        await load_seed(dut, prbs_type, seed)
        
        # Enable and check multiple outputs
        dut.enable.value = 1
        
        num_outputs = 15
        for i in range(num_outputs):
            await RisingEdge(dut.clock)
            expected_output = ref_model.generate_8_bits()
            actual_output = dut.prbs_out.value.integer
            
            assert actual_output == expected_output, (
                f"PRBS{7 if prbs_type==0 else 9 if prbs_type==1 else 15 if prbs_type==2 else 31} "
                f"output mismatch at cycle {i} with seed {hex(seed)}\n"
                f"Expected: {hex(expected_output)}\n"
                f"Got: {hex(actual_output)}"
            )
    
    dut._log.info("Random seeds test PASSED ✅")


@cocotb.test()
async def test_load_transition(dut):
    """Test that load signal transition from LOW to HIGH is required"""
    cocotb.start_soon(Clock(dut.clock, 10, units="ns").start())
    
    await reset_dut(dut)
    
    prbs_type = 0
    seed = 0x7F
    
    # Set seed and keep load LOW
    dut.prbs_type.value = prbs_type
    dut.prbs_seed.value = seed
    dut.load.value = 0
    dut.enable.value = 1
    
    # Wait a few cycles - output should remain zero
    for _ in range(5):
        await RisingEdge(dut.clock)
        assert dut.prbs_out.value.integer == 0, "Output should be zero until load transitions"
    
    # Now transition load from LOW to HIGH
    dut.load.value = 1
    await RisingEdge(dut.clock)
    dut.load.value = 0
    
    # Now output should be generated
    await RisingEdge(dut.clock)
    assert dut.prbs_out.value.integer != 0, "Output should be generated after load transition"
    
    dut._log.info("Load transition test PASSED ✅")


@cocotb.test()
async def test_asynchronous_reset(dut):
    """Test asynchronous reset functionality"""
    cocotb.start_soon(Clock(dut.clock, 10, units="ns").start())
    
    await reset_dut(dut)
    
    prbs_type = 0
    seed = 0x7F
    
    # Load seed and enable
    await load_seed(dut, prbs_type, seed)
    dut.enable.value = 1
    await RisingEdge(dut.clock)
    
    # Verify output is non-zero
    assert dut.prbs_out.value.integer != 0, "Output should be non-zero"
    
    # Apply asynchronous reset (not on clock edge)
    await Timer(5, units="ns")  # Mid-cycle
    dut.reset_n.value = 0
    
    # Check reset immediately
    await Timer(1, units="ns")
    assert dut.prbs_out.value.integer == 0, "Output should be zero immediately after async reset"
    
    # Release reset
    dut.reset_n.value = 1
    await RisingEdge(dut.clock)
    assert dut.prbs_out.value.integer == 0, "Output should be zero after reset release"
    
    dut._log.info("Asynchronous reset test PASSED ✅")


# Pytest wrapper function (required for HUD format)
def test_prbs_generator_runner():
    """Pytest wrapper for Cocotb tests"""
    import os
    from pathlib import Path
    from cocotb_tools.runner import get_runner
    
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    
    # Use sources directory for the DUT (HUD format requirement)
    sources = [proj_path / "sources/prbs_generator.sv"]
    
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="prbs_generator",
        always=True,
    )
    
    runner.test(hdl_toplevel="prbs_generator", test_module="test_prbs_generator")

