#include "llvm/Pass.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Support/raw_ostream.h"

using namespace llvm;

namespace
{

    struct FDivToMulPass : public PassInfoMixin<FDivToMulPass>
    {
        PreservedAnalyses run(Module &M, ModuleAnalysisManager &AM)
        {
            std::vector<Instruction *> toErase;

            for (auto &F : M)
            {
                for (auto &BB : F)
                {
                    for (auto &I : BB)
                    {

                        if (auto *BinOp = dyn_cast<BinaryOperator>(&I))
                        {
                            if (BinOp->getOpcode() == Instruction::FDiv)
                            {
                                errs() << "Transforming fdiv in function: " << F.getName() << "\n";

                                IRBuilder<> Builder(BinOp);
                                Value *X = BinOp->getOperand(0);
                                Value *Y = BinOp->getOperand(1);

                                if (!X->getType()->isFloatingPointTy() || !Y->getType()->isFloatingPointTy())
                                    continue;

                                // Prevent division by zero
                                if (isa<ConstantFP>(Y))
                                {
                                    auto *ConstY = cast<ConstantFP>(Y);
                                    if (ConstY->isZero())
                                        continue;
                                }

                                // Compute 1 / Y
                                Value *One = ConstantFP::get(Y->getType(), 1.0);
                                Value *Reciprocal = Builder.CreateFDiv(One, Y, "reciprocal");

                                // Replace x / y with x * (1 / y)
                                Value *NewMul = Builder.CreateFMul(X, Reciprocal, "mul_reciprocal");

                                // Store the new value explicitly
                                if (BinOp->hasOneUse())
                                {
                                    BinOp->replaceAllUsesWith(NewMul);
                                }
                                else
                                {
                                    Builder.SetInsertPoint(BinOp->getNextNode());
                                    auto *NewInst = Builder.CreateStore(NewMul, BinOp->getOperand(0));
                                    NewInst->setName("replaced_fdiv");
                                }

                                toErase.push_back(BinOp);
                            }
                        }
                    }
                }
            }

            for (Instruction *I : toErase)
            {
                I->eraseFromParent();
            }

            // Dump final LLVM IR to check if transformation happened
            errs() << "Modified LLVM IR:\n";
            M.print(errs(), nullptr);

            return PreservedAnalyses::all();
        }
    };

} // end anonymous namespace

extern "C" LLVM_ATTRIBUTE_WEAK ::llvm::PassPluginLibraryInfo llvmGetPassPluginInfo()
{
    return {
        LLVM_PLUGIN_API_VERSION, "FDivToMulPass", "v1.5",
        [](PassBuilder &PB)
        {
            PB.registerPipelineStartEPCallback(
                [](ModulePassManager &MPM, OptimizationLevel Level)
                {
                    MPM.addPass(FDivToMulPass());
                });
        }};
}