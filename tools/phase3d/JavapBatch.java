
import java.io.PrintWriter;
import java.io.StringWriter;
import java.util.Optional;
import java.util.spi.ToolProvider;

public class JavapBatch {

    public static void main(
        String[] args
    ) {

        if (args.length < 2) {

            System.err.println(
                "Usage: JavapBatch "
                + "<jar> <class> [class...]"
            );

            System.exit(2);
        }

        Optional<ToolProvider> maybe =
            ToolProvider.findFirst(
                "javap"
            );

        if (maybe.isEmpty()) {

            System.err.println(
                "javap ToolProvider "
                + "not found"
            );

            System.exit(3);
        }

        ToolProvider javap =
            maybe.get();

        String jar = args[0];

        for (
            int i = 1;
            i < args.length;
            i++
        ) {

            String cls = args[i];

            System.out.println(
                "@@BEGIN\t" + cls
            );

            StringWriter outBuffer =
                new StringWriter();

            StringWriter errBuffer =
                new StringWriter();

            PrintWriter out =
                new PrintWriter(
                    outBuffer
                );

            PrintWriter err =
                new PrintWriter(
                    errBuffer
                );

            int rc = javap.run(
                out,
                err,

                "-classpath",
                jar,

                "-c",
                "-p",
                "-s",

                cls
            );

            out.flush();
            err.flush();

            System.out.print(
                outBuffer.toString()
            );

            String errText =
                errBuffer.toString();

            if (!errText.isBlank()) {

                System.out.println(
                    "@@JAVAP_ERROR"
                );

                System.out.print(
                    errText
                );
            }

            System.out.println(
                "@@END\t"
                + cls
                + "\t"
                + rc
            );
        }
    }
}
